from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import stripe
import os
import json
from datetime import datetime
from decimal import Decimal
import logging
from dotenv import load_dotenv

load_dotenv()

# ============ CONFIG ============
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv(
    'DATABASE_URL',
    'postgresql://user:password@localhost:5432/payment_db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JSON_SORT_KEYS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
CORS(app)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLIC_KEY')

# ============ LOGGING ============
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ MODELS ============

class Customer(db.Model):
    __tablename__ = 'customers'
    
    id = db.Column(db.Integer, primary_key=True)
    stripe_customer_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    saved_cards = db.relationship('SavedCard', backref='customer', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='customer', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'stripe_customer_id': self.stripe_customer_id,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'created_at': self.created_at.isoformat()
        }

class SavedCard(db.Model):
    __tablename__ = 'saved_cards'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    stripe_payment_method_id = db.Column(db.String(255), unique=True, nullable=False)
    last4 = db.Column(db.String(4), nullable=False)
    brand = db.Column(db.String(50), nullable=False)
    exp_month = db.Column(db.Integer, nullable=False)
    exp_year = db.Column(db.Integer, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'stripe_payment_method_id': self.stripe_payment_method_id,
            'last4': self.last4,
            'brand': self.brand,
            'expiry': f"{self.exp_month:02d}/{self.exp_year}",
            'is_default': self.is_default
        }

class Transaction(db.Model):
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(255), unique=True, nullable=False)
    stripe_charge_id = db.Column(db.String(255))
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    payment_method_id = db.Column(db.Integer, db.ForeignKey('saved_cards.id'))
    description = db.Column(db.Text)
    metadata = db.Column(db.JSON)
    receipt_url = db.Column(db.Text)
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    refunds = db.relationship('Refund', backref='transaction', lazy=True, cascade='all, delete-orphan')
    payment_method = db.relationship('SavedCard')
    
    def to_dict(self):
        return {
            'id': self.id,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'stripe_charge_id': self.stripe_charge_id,
            'amount': float(self.amount),
            'currency': self.currency.upper(),
            'status': self.status,
            'description': self.description,
            'receipt_url': self.receipt_url,
            'created_at': self.created_at.isoformat(),
            'refunds': [r.to_dict() for r in self.refunds]
        }

class Refund(db.Model):
    __tablename__ = 'refunds'
    
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=False)
    stripe_refund_id = db.Column(db.String(255), unique=True, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    reason = db.Column(db.String(100))
    status = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'stripe_refund_id': self.stripe_refund_id,
            'amount': float(self.amount),
            'reason': self.reason,
            'status': self.status,
            'created_at': self.created_at.isoformat()
        }

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer)
    old_data = db.Column(db.JSON)
    new_data = db.Column(db.JSON)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ============ AUDIT LOG HELPER ============

def log_action(action, entity_type, entity_id, old_data=None, new_data=None):
    """تسجيل جميع الإجراءات"""
    try:
        log = AuditLog(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            old_data=old_data,
            new_data=new_data,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f"Error logging action: {str(e)}")

# ============ API ENDPOINTS ============

@app.route('/api/config', methods=['GET'])
def config():
    """الحصول على Stripe Config"""
    return jsonify({'publishableKey': PUBLISHABLE_KEY})

# ========== CUSTOMER MANAGEMENT ==========

@app.route('/api/customers', methods=['POST'])
def create_customer():
    """إنشاء عميل جديد"""
    try:
        data = request.json
        
        # التحقق من عدم وجود عميل بنفس البريد
        existing = Customer.query.filter_by(email=data.get('email')).first()
        if existing:
            return jsonify({
                'status': 'error',
                'message': 'العميل موجود بالفعل',
                'customer_id': existing.id
            }), 400
        
        # إنشاء في Stripe
        stripe_customer = stripe.Customer.create(
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone', ''),
            description=f"Customer: {data.get('name')}"
        )
        
        # حفظ في DB
        customer = Customer(
            stripe_customer_id=stripe_customer.id,
            name=data.get('name'),
            email=data.get('email'),
            phone=data.get('phone', '')
        )
        
        db.session.add(customer)
        db.session.commit()
        
        log_action('CREATE', 'customer', customer.id, new_data=customer.to_dict())
        
        return jsonify({
            'status': 'success',
            'customer': customer.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating customer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/customers/<int:customer_id>', methods=['GET'])
def get_customer(customer_id):
    """الحصول على بيانات العميل"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({
                'status': 'error',
                'message': 'العميل غير موجود'
            }), 404
        
        return jsonify({
            'status': 'success',
            'customer': customer.to_dict()
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching customer: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========== CARD MANAGEMENT ==========

@app.route('/api/customers/<int:customer_id>/cards', methods=['GET'])
def list_customer_cards(customer_id):
    """إظهار جميع البطاقات المحفوظة للعميل"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({
                'status': 'error',
                'message': 'العميل غير موجود'
            }), 404
        
        cards = [card.to_dict() for card in customer.saved_cards]
        
        return jsonify({
            'status': 'success',
            'count': len(cards),
            'cards': cards
        }), 200
        
    except Exception as e:
        logger.error(f"Error listing cards: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/customers/<int:customer_id>/cards', methods=['POST'])
def add_card(customer_id):
    """حفظ بطاقة جديدة"""
    try:
        data = request.json
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({
                'status': 'error',
                'message': 'العميل غير موجود'
            }), 404
        
        # إنشاء Payment Method في Stripe
        payment_method = stripe.PaymentMethod.create(
            type='card',
            card={
                'number': data.get('card_number').replace(' ', ''),
                'exp_month': data.get('exp_month'),
                'exp_year': data.get('exp_year'),
                'cvc': data.get('cvc')
            },
            billing_details={
                'name': data.get('name')
            }
        )
        
        # ربط مع العميل
        stripe.PaymentMethod.attach(
            payment_method.id,
            customer=customer.stripe_customer_id
        )
        
        # حفظ في DB
        saved_card = SavedCard(
            customer_id=customer_id,
            stripe_payment_method_id=payment_method.id,
            last4=payment_method.card.last4,
            brand=payment_method.card.brand.upper(),
            exp_month=payment_method.card.exp_month,
            exp_year=payment_method.card.exp_year,
            is_default=data.get('is_default', False)
        )
        
        db.session.add(saved_card)
        db.session.commit()
        
        log_action('CREATE', 'saved_card', saved_card.id, new_data=saved_card.to_dict())
        
        return jsonify({
            'status': 'success',
            'card': saved_card.to_dict()
        }), 201
        
    except stripe.error.CardError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f"Card Error: {e.user_message}"
        }), 400
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/cards/<int:card_id>', methods=['DELETE'])
def delete_card(card_id):
    """حذف بطاقة"""
    try:
        card = SavedCard.query.get(card_id)
        if not card:
            return jsonify({
                'status': 'error',
                'message': 'البطاقة غير موجودة'
            }), 404
        
        # حذف من Stripe
        stripe.PaymentMethod.detach(card.stripe_payment_method_id)
        
        # حذف من DB
        card_data = card.to_dict()
        db.session.delete(card)
        db.session.commit()
        
        log_action('DELETE', 'saved_card', card_id, old_data=card_data)
        
        return jsonify({
            'status': 'success',
            'message': 'تم حذف البطاقة'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error deleting card: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========== PAYMENT PROCESSING ==========

@app.route('/api/payments', methods=['POST'])
def process_payment():
    """معالجة الدفع"""
    try:
        data = request.json
        
        customer = Customer.query.get(data.get('customer_id'))
        if not customer:
            return jsonify({
                'status': 'error',
                'message': 'العميل غير موجود'
            }), 404
        
        # إنشاء Payment Intent
        intent = stripe.PaymentIntent.create(
            amount=int(data.get('amount') * 100),
            currency=data.get('currency', 'usd'),
            customer=customer.stripe_customer_id,
            payment_method=data.get('payment_method_id'),
            off_session=True,
            confirm=True,
            description=data.get('description')
        )
        
        # حفظ في DB
        transaction = Transaction(
            customer_id=customer.id,
            stripe_payment_intent_id=intent.id,
            stripe_charge_id=intent.charges.data[0].id if intent.charges.data else None,
            amount=Decimal(str(data.get('amount'))),
            currency=data.get('currency', 'usd'),
            status=intent.status,
            payment_method_id=data.get('payment_method_id'),
            description=data.get('description'),
            receipt_url=intent.charges.data[0].receipt_url if intent.charges.data else None
        )
        
        db.session.add(transaction)
        db.session.commit()
        
        log_action('CREATE', 'transaction', transaction.id, new_data=transaction.to_dict())
        
        if intent.status == 'succeeded':
            return jsonify({
                'status': 'success',
                'message': 'تم الدفع بنجاح',
                'transaction': transaction.to_dict()
            }), 200
        else:
            return jsonify({
                'status': 'failed',
                'message': f'فشل الدفع: {intent.status}',
                'transaction': transaction.to_dict()
            }), 400
            
    except stripe.error.CardError as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f"Card Error: {e.user_message}"
        }), 400
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing payment: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========== TRANSACTION HISTORY ==========

@app.route('/api/customers/<int:customer_id>/transactions', methods=['GET'])
def get_customer_transactions(customer_id):
    """سجل المعاملات"""
    try:
        customer = Customer.query.get(customer_id)
        if not customer:
            return jsonify({
                'status': 'error',
                'message': 'العميل غير موجود'
            }), 404
        
        # Pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        transactions = Transaction.query.filter_by(customer_id=customer_id)\
            .order_by(Transaction.created_at.desc())\
            .paginate(page=page, per_page=per_page)
        
        return jsonify({
            'status': 'success',
            'total': transactions.total,
            'pages': transactions.pages,
            'current_page': page,
            'transactions': [t.to_dict() for t in transactions.items]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching transactions: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========== REFUNDS ==========

@app.route('/api/transactions/<int:transaction_id>/refund', methods=['POST'])
def refund_transaction(transaction_id):
    """استرجاع مبلغ"""
    try:
        data = request.json
        transaction = Transaction.query.get(transaction_id)
        
        if not transaction:
            return jsonify({
                'status': 'error',
                'message': 'المعاملة غير موجودة'
            }), 404
        
        if transaction.status != 'succeeded':
            return jsonify({
                'status': 'error',
                'message': 'لا يمكن استرجاع معاملة لم تنجح'
            }), 400
        
        # إنشاء استرجاع في Stripe
        refund = stripe.Refund.create(
            payment_intent=transaction.stripe_payment_intent_id,
            amount=int(data.get('amount', transaction.amount) * 100) if data.get('amount') else None,
            reason=data.get('reason', 'requested_by_customer')
        )
        
        # حفظ في DB
        refund_record = Refund(
            transaction_id=transaction_id,
            stripe_refund_id=refund.id,
            amount=Decimal(str(data.get('amount', transaction.amount))),
            reason=data.get('reason'),
            status=refund.status
        )
        
        db.session.add(refund_record)
        db.session.commit()
        
        log_action('CREATE', 'refund', refund_record.id, new_data=refund_record.to_dict())
        
        return jsonify({
            'status': 'success',
            'message': 'تم استرجاع المبلغ',
            'refund': refund_record.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error processing refund: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ========== AUDIT LOGS ==========

@app.route('/api/audit-logs', methods=['GET'])
def get_audit_logs():
    """عرض سجل جميع الإجراءات"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        logs = AuditLog.query\
            .order_by(AuditLog.created_at.desc())\
            .paginate(page=page, per_page=per_page)
        
        return jsonify({
            'status': 'success',
            'total': logs.total,
            'logs': [{
                'id': log.id,
                'action': log.action,
                'entity_type': log.entity_type,
                'entity_id': log.entity_id,
                'created_at': log.created_at.isoformat()
            } for log in logs.items]
        }), 200
        
    except Exception as e:
        logger.error(f"Error fetching audit logs: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# ============ ERROR HANDLERS ============

@app.errorhandler(404)
def not_found(error):
    return jsonify({'status': 'error', 'message': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

# ============ HEALTH CHECK ============

@app.route('/health', methods=['GET'])
def health():
    """فحص صحة الـ API"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.utcnow().isoformat()
    }), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    
    port = int(os.getenv('PORT', 8000))
    app.run(debug=False, host='0.0.0.0', port=port)
