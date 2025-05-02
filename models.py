from datetime import datetime
from main import db

class SoldTicket(db.Model):
    """Model to track tickets that have been sold"""
    __tablename__ = 'sold_tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    pnr_number = db.Column(db.String(50), unique=True, nullable=False)
    from_location = db.Column(db.String(100), nullable=False)
    to_location = db.Column(db.String(100), nullable=False)
    travel_date = db.Column(db.Date, nullable=False)
    train_number = db.Column(db.String(50), nullable=False)
    sold_at = db.Column(db.DateTime, default=datetime.utcnow)
    buyer_email = db.Column(db.String(120), nullable=True)  # Email of the buyer for ticket delivery
    payment_id = db.Column(db.String(120), nullable=True)  # Stripe payment ID
    seller_id = db.Column(db.Integer, nullable=True)  # Seller ID to track who sold the ticket
    from_ticket_id = db.Column(db.Integer, nullable=True)  # Original ticket ID for reference to chat
    
    def __repr__(self):
        return f'<SoldTicket {self.id}: PNR {self.pnr_number}>'

class Ticket(db.Model):
    """Model for train tickets being resold"""
    __tablename__ = 'tickets'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    
    # Train ticket specific fields
    pnr_number = db.Column(db.String(50), nullable=False)
    from_location = db.Column(db.String(100), nullable=False)
    to_location = db.Column(db.String(100), nullable=False)
    travel_date = db.Column(db.Date, nullable=False)
    train_number = db.Column(db.String(50), nullable=False)
    passenger_name = db.Column(db.String(100), nullable=False)
    
    # Ticket status and seller info
    seller_id = db.Column(db.Integer, nullable=True)  # Will be used when we add user authentication
    is_expired = db.Column(db.Boolean, default=False)
    
    # Payment tracking
    stripe_checkout_id = db.Column(db.String(120), nullable=True)  # Stripe checkout session ID
    payment_status = db.Column(db.String(20), nullable=True)  # 'pending', 'completed', 'failed'
    buyer_email = db.Column(db.String(120), nullable=True)  # Email of the buyer for confirmation
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Ticket {self.id}: {self.from_location} to {self.to_location}>'
    
    def to_dict(self):
        """Convert ticket to dictionary for easy serialization"""
        return {
            'id': self.id,
            'title': self.title,
            'price': self.price,
            'description': self.description,
            'filename': self.filename,
            'pnr_number': self.pnr_number,
            'from_location': self.from_location,
            'to_location': self.to_location,
            'travel_date': self.travel_date.strftime('%Y-%m-%d'),
            'train_number': self.train_number,
            'passenger_name': self.passenger_name,
            'is_expired': self.is_expired,
            'payment_status': self.payment_status,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S')
        }

class Message(db.Model):
    """Model for chat messages between sellers and buyers"""
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, db.ForeignKey('tickets.id'), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # 'buyer' or 'seller'
    message_text = db.Column(db.Text, nullable=False)
    is_ticket_shared = db.Column(db.Boolean, default=False)  # Flag for when ticket is shared
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to ticket
    ticket = db.relationship('Ticket', backref=db.backref('messages', lazy=True))
    
    def __repr__(self):
        return f'<Message {self.id}: {self.sender_type}>'

class SellerWallet(db.Model):
    """Model for seller's wallet to receive payments"""
    __tablename__ = 'seller_wallets'
    
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, nullable=False)  # For now, this will be a mock ID
    balance = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='INR')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SellerWallet {self.id}: Balance {self.balance} {self.currency}>'

class WalletTransaction(db.Model):
    """Model to track wallet transactions"""
    __tablename__ = 'wallet_transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    wallet_id = db.Column(db.Integer, db.ForeignKey('seller_wallets.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(10), nullable=False)  # 'credit' or 'debit'
    description = db.Column(db.String(255), nullable=True)
    payment_id = db.Column(db.String(120), nullable=True)  # Stripe payment ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    wallet = db.relationship('SellerWallet', backref=db.backref('transactions', lazy=True))
    
    def __repr__(self):
        return f'<WalletTransaction {self.id}: {self.transaction_type} {self.amount}>'