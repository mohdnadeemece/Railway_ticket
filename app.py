from flask import render_template, request, redirect, url_for, flash, jsonify
from werkzeug.utils import secure_filename
import os
import logging
from datetime import datetime, date
from data.indian_cities import INDIAN_RAILWAY_CITIES
import re

# Import app and models from main
from main import app, db
from models import Ticket, SoldTicket, Message, SellerWallet, WalletTransaction

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Debug database URL
logging.debug(f"Using database URL: {os.environ.get('DATABASE_URL')}")

# Setup upload folder
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size

# Configure allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png', 'svg', 'gif'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def validate_pnr(pnr_number):
    """
    Validate the format of a PNR number and check if it's already sold
    Returns (is_valid, error_message)
    """
    # Check if PNR follows the correct pattern (10 digits)
    if not re.match(r'^\d{10}$', pnr_number):
        return False, "PNR must be exactly 10 digits"
    
    # Check if PNR is already in the sold tickets database
    sold_ticket = SoldTicket.query.filter_by(pnr_number=pnr_number).first()
    if sold_ticket:
        return False, "This ticket has already been sold and cannot be resold"
    
    return True, ""

def check_expired_tickets():
    """Check for tickets with travel dates in the past and mark them as expired"""
    today = date.today()
    expired_tickets = Ticket.query.filter(
        Ticket.travel_date < today,
        Ticket.is_expired == False
    ).all()
    
    for ticket in expired_tickets:
        ticket.is_expired = True
    
    if expired_tickets:
        try:
            db.session.commit()
            logging.info(f"Marked {len(expired_tickets)} tickets as expired")
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error marking tickets as expired: {str(e)}")

@app.route('/')
def index():
    # Check for expired tickets on each page load
    check_expired_tickets()
    
    from_location = request.args.get('from', '')
    to_location = request.args.get('to', '')
    
    # Query the database with filters - only show non-expired tickets
    query = Ticket.query.filter_by(is_expired=False)
    
    if from_location and to_location:
        # Filter by both from and to locations
        query = query.filter(
            Ticket.from_location.ilike(f"%{from_location}%"),
            Ticket.to_location.ilike(f"%{to_location}%")
        )
    elif from_location:
        # Filter by from location only
        query = query.filter(Ticket.from_location.ilike(f"%{from_location}%"))
    elif to_location:
        # Filter by to location only
        query = query.filter(Ticket.to_location.ilike(f"%{to_location}%"))
    
    # Order by most recently added
    tickets = query.order_by(Ticket.created_at.desc()).all()
    
    return render_template('index.html', 
                          tickets=tickets,
                          from_location=from_location,
                          to_location=to_location,
                          cities=INDIAN_RAILWAY_CITIES)

@app.route('/upload', methods=['GET', 'POST'])
def upload_ticket():
    if request.method == 'POST':
        # Form validation
        if 'title' not in request.form or not request.form['title'].strip():
            flash('Please provide a ticket title', 'danger')
            return redirect(url_for('upload_ticket'))
            
        if 'price' not in request.form or not request.form['price'].strip():
            flash('Please provide a ticket price', 'danger')
            return redirect(url_for('upload_ticket'))
        
        try:
            price = float(request.form['price'])
            if price <= 0:
                flash('Price must be greater than zero', 'danger')
                return redirect(url_for('upload_ticket'))
        except ValueError:
            flash('Price must be a valid number', 'danger')
            return redirect(url_for('upload_ticket'))
            
        # Check if file was submitted
        if 'file' not in request.files:
            flash('No file part', 'danger')
            return redirect(url_for('upload_ticket'))
            
        file = request.files['file']
        
        # Check if file was selected
        if file.filename == '':
            flash('No image selected for uploading', 'danger')
            return redirect(url_for('upload_ticket'))
        
        # Get ticket information
        title = request.form['title']
        price = float(request.form['price'])
        description = request.form.get('description', '')
        
        # Get train ticket details
        from_location = request.form.get('from_location', '')
        to_location = request.form.get('to_location', '')
        travel_date_str = request.form.get('travel_date', '')
        train_number = request.form.get('train_number', '')
        passenger_name = request.form.get('passenger_name', '')
        pnr_number = request.form.get('pnr_number', '')
        
        # Validate required train ticket fields
        if not from_location:
            flash('Please provide origin location', 'danger')
            return redirect(url_for('upload_ticket'))
            
        if not to_location:
            flash('Please provide destination location', 'danger')
            return redirect(url_for('upload_ticket'))
            
        if not travel_date_str:
            flash('Please provide travel date', 'danger')
            return redirect(url_for('upload_ticket'))
            
        if not train_number:
            flash('Please provide train number', 'danger')
            return redirect(url_for('upload_ticket'))
            
        if not passenger_name:
            flash('Please provide passenger name', 'danger')
            return redirect(url_for('upload_ticket'))
            
        if not pnr_number:
            flash('Please provide the PNR number', 'danger')
            return redirect(url_for('upload_ticket'))
            
        # Validate PNR number
        is_valid_pnr, pnr_error = validate_pnr(pnr_number)
        if not is_valid_pnr:
            flash(pnr_error, 'danger')
            return redirect(url_for('upload_ticket'))
        
        # Parse and validate travel date
        try:
            travel_date = datetime.strptime(travel_date_str, '%Y-%m-%d').date()
        except ValueError:
            flash('Invalid travel date format. Please use YYYY-MM-DD format', 'danger')
            return redirect(url_for('upload_ticket'))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            # Create and save new ticket to database
            new_ticket = Ticket(
                title=title,
                price=price,
                description=description,
                filename=filename,
                pnr_number=pnr_number,
                from_location=from_location,
                to_location=to_location,
                travel_date=travel_date,
                train_number=train_number,
                passenger_name=passenger_name,
                is_expired=False
            )
            
            try:
                db.session.add(new_ticket)
                db.session.commit()
                flash('Ticket uploaded successfully!', 'success')
                return redirect(url_for('index'))
            except Exception as e:
                db.session.rollback()
                logging.error(f"Database error: {str(e)}")
                flash('Error saving ticket to database', 'danger')
                return redirect(url_for('upload_ticket'))
        else:
            flash('Allowed image types are: png, jpg, jpeg, gif', 'danger')
            return redirect(url_for('upload_ticket'))

    return render_template('upload.html', cities=INDIAN_RAILWAY_CITIES)

@app.route('/buy/<int:ticket_id>')
def buy_ticket(ticket_id):
    logging.debug(f"Buying ticket ID: {ticket_id}")
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        logging.debug(f"Found ticket: {ticket.id} - {ticket.title}")
        original_price = ticket.price
        commission = original_price * 0.10
        total_price = original_price + commission
        
        # Start a chat for this ticket
        return redirect(url_for('chat', ticket_id=ticket.id))
    else:
        logging.error(f"Ticket not found with ID: {ticket_id}")
        flash("Ticket not found.", 'danger')
        return redirect(url_for('index'))

import os
import stripe
from flask import send_file
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)

# Setup Stripe
stripe_key = os.environ.get('STRIPE_SECRET_KEY')
if not stripe_key:
    logging.error("STRIPE_SECRET_KEY environment variable is not set!")
else:
    logging.info(f"Stripe API key configured: {stripe_key[:4]}...{stripe_key[-4:]}")

stripe.api_key = stripe_key
YOUR_DOMAIN = os.environ.get('REPLIT_DEV_DOMAIN', 'localhost:5000')
if not YOUR_DOMAIN.startswith(('http://', 'https://')):
    YOUR_DOMAIN = f"https://{YOUR_DOMAIN}"
logging.info(f"Domain configured as: {YOUR_DOMAIN}")
    
@app.route('/request_release/<int:ticket_id>')
def request_release(ticket_id):
    """Buyer requests the seller to release the ticket"""
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        # Check if there is already a release request pending
        release_request_message = Message.query.filter_by(
            ticket_id=ticket_id, 
            sender_type='buyer',
            message_text='[SYSTEM] Buyer has requested the ticket to be released.'
        ).first()
        
        if release_request_message:
            flash("You have already requested this ticket to be released. Please wait for the seller to confirm.", "warning")
        else:
            # Create a system message to request release
            release_request = Message(
                ticket_id=ticket_id,
                sender_type='buyer',
                message_text='[SYSTEM] Buyer has requested the ticket to be released.',
                is_ticket_shared=False
            )
            
            try:
                db.session.add(release_request)
                db.session.commit()
                flash("Release request sent to the seller.", "success")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error creating release request: {str(e)}")
                flash("Error sending release request.", "danger")
    else:
        flash("Ticket not found.", "danger")
    
    return redirect(url_for('chat', ticket_id=ticket_id))

@app.route('/release_ticket/<int:ticket_id>')
def release_ticket(ticket_id):
    """Seller confirms and releases the ticket to the buyer"""
    ticket = Ticket.query.get(ticket_id)
    if ticket:
        # Check if the PNR has been shared
        shared_message = Message.query.filter_by(
            ticket_id=ticket_id, 
            sender_type='seller',
            is_ticket_shared=True
        ).first()
        
        if not shared_message:
            flash("You must first share the ticket details before releasing it.", "warning")
            return redirect(url_for('chat', ticket_id=ticket_id))
        
        # Add confirmation message
        confirmation = Message(
            ticket_id=ticket_id,
            sender_type='seller',
            message_text='[SYSTEM] Seller has confirmed the ticket transfer.',
            is_ticket_shared=False
        )
        
        try:
            db.session.add(confirmation)
            db.session.commit()
            
            # Redirect to payment page instead of finalizing purchase directly
            return redirect(url_for('payment_page', ticket_id=ticket_id))
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error adding confirmation message: {str(e)}")
            flash("Error confirming release. Please try again.", "danger")
            return redirect(url_for('chat', ticket_id=ticket_id))
    else:
        flash("Ticket not found.", "danger")
        return redirect(url_for('index'))

@app.route('/payment/<int:ticket_id>')
def payment_page(ticket_id):
    """Show payment page for the ticket"""
    logging.debug(f"Accessing payment page for ticket ID: {ticket_id}")
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        logging.error(f"Payment page - Ticket not found with ID: {ticket_id}")
        flash("Ticket not found.", "danger")
        return redirect(url_for('index'))
    
    # Check if ticket has already been sold
    existing_sold_ticket = SoldTicket.query.filter_by(pnr_number=ticket.pnr_number).first()
    if existing_sold_ticket:
        logging.warning(f"Attempt to purchase already sold ticket with PNR: {ticket.pnr_number}")
        flash("This ticket has already been sold.", "danger")
        return redirect(url_for('index'))
    
    logging.debug(f"Showing payment page for ticket: {ticket.title}")
    return render_template('payment.html', ticket=ticket)

@app.route('/process_payment/<int:ticket_id>', methods=['POST'])
def process_payment(ticket_id):
    """Create Stripe checkout session for ticket payment"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        flash("Ticket not found.", "danger")
        return redirect(url_for('index'))
    
    buyer_email = request.form.get('email')
    if not buyer_email:
        flash("Email is required for ticket delivery.", "danger")
        return redirect(url_for('payment_page', ticket_id=ticket_id))
    
    # Store buyer email in ticket record
    ticket.buyer_email = buyer_email
    
    # Calculate price in smallest currency unit (cents/paise)
    price_with_commission = int(ticket.price * 110)  # Including 10% commission
    
    try:
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {
                            'name': ticket.title,
                            'description': f'From {ticket.from_location} to {ticket.to_location} on {ticket.travel_date.strftime("%d-%m-%Y")}',
                        },
                        'unit_amount': price_with_commission,
                    },
                    'quantity': 1,
                },
            ],
            metadata={
                'ticket_id': ticket.id,
                'pnr_number': ticket.pnr_number,
                'buyer_email': buyer_email,
            },
            mode='payment',
            success_url=YOUR_DOMAIN + url_for('payment_success', session_id='{CHECKOUT_SESSION_ID}'),
            cancel_url=YOUR_DOMAIN + url_for('payment_cancel', ticket_id=ticket.id),
        )
        
        # Update ticket with checkout session ID
        ticket.stripe_checkout_id = checkout_session.id
        ticket.payment_status = 'pending'
        db.session.commit()
        
        # Redirect to Stripe checkout
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        logging.error(f"Error creating Stripe session: {str(e)}")
        flash("Payment processing error. Please try again.", "danger")
        return redirect(url_for('payment_page', ticket_id=ticket_id))

@app.route('/payment/success')
def payment_success():
    """Handle successful payment return from Stripe"""
    session_id = request.args.get('session_id')
    if not session_id:
        flash("Invalid payment session.", "danger")
        return redirect(url_for('index'))
    
    try:
        # Get checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # Get ticket ID from metadata
        ticket_id = int(checkout_session.metadata.get('ticket_id'))
        
        # Add a message in the chat showing the ticket has been purchased
        ticket = Ticket.query.get(ticket_id)
        if ticket:
            purchase_message = Message(
                ticket_id=ticket_id,
                sender_type='system',
                message_text=f'[SYSTEM] Ticket has been successfully purchased by {ticket.buyer_email}',
                is_ticket_shared=True
            )
            try:
                db.session.add(purchase_message)
                db.session.commit()
                logging.info(f"Added purchase confirmation message for ticket {ticket_id}")
            except Exception as e:
                db.session.rollback()
                logging.error(f"Error adding purchase message: {str(e)}")
        
        # Render success page
        return render_template('payment_success.html', session_id=session_id, checkout_session=checkout_session)
    except Exception as e:
        logging.error(f"Error processing payment success: {str(e)}")
        flash("Error verifying payment. Please contact support.", "danger")
        return redirect(url_for('index'))

@app.route('/payment/cancel/<int:ticket_id>')
def payment_cancel(ticket_id):
    """Handle cancelled payment return from Stripe"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        flash("Ticket not found.", "danger")
        return redirect(url_for('index'))
    
    # Update ticket payment status
    ticket.payment_status = 'cancelled'
    db.session.commit()
    
    return render_template('payment_cancel.html', ticket_id=ticket_id)

@app.route('/view_purchased_ticket/<session_id>')
def view_purchased_ticket(session_id):
    """View purchased ticket after successful payment"""
    try:
        # Get checkout session from Stripe
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        payment_intent = stripe.PaymentIntent.retrieve(checkout_session.payment_intent)
        
        # Get ticket ID from metadata
        ticket_id = int(checkout_session.metadata.get('ticket_id'))
        ticket = Ticket.query.get(ticket_id)
        
        if not ticket:
            flash("Ticket not found. It may have already been processed.", "warning")
            return redirect(url_for('index'))
        
        # Finalize the purchase
        try:
            # Get seller wallet or create one if it doesn't exist
            seller_wallet = SellerWallet.query.filter_by(seller_id=ticket.seller_id or 1).first()
            if not seller_wallet:
                seller_wallet = SellerWallet(seller_id=ticket.seller_id or 1)
                db.session.add(seller_wallet)
                db.session.commit()
            
            # Calculate payment amounts
            original_price = ticket.price
            commission = original_price * 0.10
            seller_amount = original_price
            
            # Create sold ticket record
            sold_ticket = SoldTicket(
                pnr_number=ticket.pnr_number,
                from_location=ticket.from_location,
                to_location=ticket.to_location,
                travel_date=ticket.travel_date,
                train_number=ticket.train_number,
                buyer_email=ticket.buyer_email,
                payment_id=payment_intent.id,
                seller_id=ticket.seller_id,
                from_ticket_id=ticket.id  # Store original ticket ID for reference
            )
            
            # Add funds to seller wallet
            seller_wallet.balance += seller_amount
            
            # Create wallet transaction record
            wallet_transaction = WalletTransaction(
                wallet_id=seller_wallet.id,
                amount=seller_amount,
                transaction_type='credit',
                description=f'Payment for ticket {ticket.id}: {ticket.from_location} to {ticket.to_location}',
                payment_id=payment_intent.id
            )
            
            # Save all changes
            db.session.add(sold_ticket)
            db.session.add(wallet_transaction)
            ticket.payment_status = 'completed'
            db.session.commit()
            
            # Return ticket download page
            return render_template('ticket_download.html', 
                                  sold_ticket=sold_ticket, 
                                  payment_id=payment_intent.id,
                                  ticket_filename=ticket.filename)
            
        except Exception as e:
            db.session.rollback()
            logging.error(f"Error finalizing purchase: {str(e)}")
            flash("Error processing your purchase. Please contact support.", "danger")
            return redirect(url_for('index'))
        
    except Exception as e:
        logging.error(f"Error retrieving payment info: {str(e)}")
        flash("Error verifying payment. Please contact support.", "danger")
        return redirect(url_for('index'))

@app.route('/download_ticket/<int:sold_ticket_id>')
def download_ticket(sold_ticket_id):
    """Download purchased ticket"""
    sold_ticket = SoldTicket.query.get(sold_ticket_id)
    if not sold_ticket:
        flash("Ticket not found.", "danger")
        return redirect(url_for('index'))
    
    try:
        # Get the ticket image
        ticket_path = os.path.join(app.config['UPLOAD_FOLDER'], sold_ticket.pnr_number + '.svg')
        
        # If actual file doesn't exist with PNR as filename, look for it in uploads directory
        if not os.path.exists(ticket_path):
            # Find any file that matches in the uploads directory
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                if filename.endswith('.svg'):
                    ticket_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    break
        
        # Send file as download attachment
        return send_file(ticket_path, 
                        mimetype='image/svg+xml', 
                        as_attachment=True,
                        download_name=f"Ticket_{sold_ticket.from_location}_to_{sold_ticket.to_location}.svg")
    except Exception as e:
        logging.error(f"Error downloading ticket: {str(e)}")
        flash("Error downloading ticket. Please try again.", "danger")
        return redirect(url_for('index'))

@app.route('/finalize_purchase/<int:ticket_id>')
def finalize_purchase(ticket_id):
    """Redirect to payment page (kept for backward compatibility)"""
    return redirect(url_for('payment_page', ticket_id=ticket_id))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Adding the missing imports
from flask import send_from_directory, session

# Chat functionality
@app.route('/chat/<int:ticket_id>')
def chat(ticket_id):
    """Chat interface for buyer and seller"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        flash("Ticket not found.", "danger")
        return redirect(url_for('index'))
    
    # Set a session variable to remember if this is the buyer or seller
    # In a real app, this would be based on user login
    if 'user_type' not in session:
        session['user_type'] = 'buyer'  # Default to buyer for this demo
    
    messages = Message.query.filter_by(ticket_id=ticket_id).order_by(Message.created_at.asc()).all()
    
    return render_template('chat.html', 
                          ticket=ticket, 
                          messages=messages, 
                          user_type=session['user_type'])

@app.route('/send_message/<int:ticket_id>', methods=['POST'])
def send_message(ticket_id):
    """API to send a message in the chat"""
    ticket = Ticket.query.get(ticket_id)
    if not ticket:
        return jsonify({"success": False, "error": "Ticket not found"})
    
    message_text = request.form.get('message', '').strip()
    if not message_text:
        return jsonify({"success": False, "error": "Message cannot be empty"})
    
    # Get user type from session (buyer or seller)
    user_type = session.get('user_type', 'buyer')
    
    # Check if this is a ticket sharing message from seller
    is_ticket_shared = 'share_ticket' in request.form and user_type == 'seller'
    
    # Create and save the message
    new_message = Message(
        ticket_id=ticket_id,
        sender_type=user_type,
        message_text=message_text,
        is_ticket_shared=is_ticket_shared
    )
    
    try:
        db.session.add(new_message)
        db.session.commit()
        
        # If ticket was shared, return a special response
        if is_ticket_shared:
            return jsonify({
                "success": True,
                "shared": True,
                "message": "Ticket has been shared with the buyer"
            })
        
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error saving message: {str(e)}")
        return jsonify({"success": False, "error": "Database error"})

@app.route('/switch_user/<user_type>')
def switch_user(user_type):
    """Helper function to switch between buyer and seller modes"""
    if user_type in ['buyer', 'seller']:
        session['user_type'] = user_type
        flash(f"Switched to {user_type} mode", "info")
    return redirect(request.referrer or url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
