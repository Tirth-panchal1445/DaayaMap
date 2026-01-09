import os
import json
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS  
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
from datetime import datetime
import requests
import base64

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True) 

firebase_config_json = os.getenv('FIREBASE_CONFIG')

if firebase_config_json:
    try:
        firebase_config = json.loads(firebase_config_json)
        cred = credentials.Certificate(firebase_config)
        firebase_admin.initialize_app(cred, {
            'storageBucket': 'top-amplifier-483709-g3.appspot.com'
        })
        print("✅ Firebase initialized successfully!")
    except Exception as e:
        print(f"❌ Firebase initialization error: {e}")
        cred = None
else:
    print("❌ FIREBASE_CONFIG environment variable not found!")
    cred = None

db = firestore.client()
bucket = storage.bucket()


# ============= HELPER FUNCTION =============

def upload_to_imgbb(file):
    """Upload file to ImgBB and return URL"""
    if not file or file.filename == '':
        return None
    
    try:
        api_key = 'b08ffd05a12bfdbc82cda7b9cc8a43d2'
        api_url = "https://api.imgbb.com/1/upload"
        
        file_content = file.read()
        
        payload = {"key": api_key}
        files = {"image": (file.filename, file_content)}
        
        response = requests.post(api_url, data=payload, files=files, timeout=30)
        
        if response.status_code == 200:
            res_data = response.json()
            if res_data.get('success'):
                return res_data['data']['url']
        
        return None
        
    except Exception as e:
        print(f"ImgBB upload error: {e}")
        return None


# ============= ROUTES FOR NEW FRONTEND =============

# Main auth page
@app.route('/')
def index():
    return render_template('auth.html')

# Donor dashboard
@app.route('/donate')
def donate_page():
    return render_template('donor_dash.html')

# NGO dashboard  
@app.route('/mainmap')
def mainmap_page():
    return render_template('ngo_dash.html')


# ============= API ENDPOINTS =============

# Registration
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user_type = data.get('user_type')
    
    if not email or not password or not user_type:
        return jsonify({'error': 'Email and password are required'})
    
    try:
        user = auth.create_user(email=email, password=password)
        user_id = user.uid
        print(f"Created user: {user_id}")

        user_data = {
            'email': email, 
            'user_type': user_type, 
            'created_at': datetime.now().isoformat(),
            'reputation_score': 0  # Initialize reputation
        }

        # Donor-specific fields
        if user_type == 'donor':
            user_data['restaurant_name'] = data.get('restaurant_name')
            user_data['fssai_id'] = data.get('fssai_id')
            user_data['aadhar_image'] = data.get('aadhar_image_url')

        # NGO-specific fields
        elif user_type == 'ngo':
            user_data['ngo_name'] = data.get('ngo_name')
            user_data['ngo_certificate_image'] = data.get('ngo_certificate_url')
            user_data['worker_id_image'] = data.get('worker_id_url')

        db.collection('users').document(user_id).set(user_data)
        print(f"Saved user data")
        
        return jsonify({
            'message': 'Registration successful',
            'user_id': user_id,
            'user_type': user_type
        })
        
    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({'error': str(e)})


# Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'})
    
    try:
        user = auth.get_user_by_email(email)
        user_id = user.uid
        
        user_doc = db.collection('users').document(user_id).get()
        
        if not user_doc.exists:
            return jsonify({'error': 'User not found'})
        
        user_data = user_doc.to_dict()
        user_type = user_data.get('user_type')
        
        print(f"User {user_id} logged in")
        
        return jsonify({
            'message': 'Login successful', 
            'user_id': user_id, 
            'user_type': user_type,
            'reputation_score': user_data.get('reputation_score', 0)
        })
    
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'Invalid credentials'})


# Create listing
@app.route('/create_listing', methods=['POST'])
def create_listing():
    donor_id = request.form.get('donor_id')
    food_name = request.form.get('food_name')
    quantity = request.form.get('quantity')
    latitude = request.form.get('latitude')
    longitude = request.form.get('longitude')
    expiry_date = request.form.get('expiry_date')
    veg_nonveg = request.form.get('veg_nonveg')
    address = request.form.get('address')
    age_group = request.form.get('age_group')
    description = request.form.get('description')

    food_image = request.files.get('food_image')
    image_url = ""

    if not donor_id or not food_name or not latitude:
        return jsonify({'error': 'Please fill all required fields'})

    try:
        # Upload image if provided
        if food_image:
            image_url = upload_to_imgbb(food_image)
            if not image_url:
                image_url = ""

        # Create listing
        listing_data = {
            'donor_id': donor_id,
            'food_name': food_name,
            'quantity': quantity,
            'latitude': float(latitude),
            'longitude': float(longitude),
            'expiry_date': expiry_date,
            'status': 'available',
            'image_url': image_url,
            'created_at': datetime.now().isoformat(),
            'veg_nonveg': veg_nonveg,
            'description': description,
            'age_group': age_group,
            'address': address
        }
        
        listing_ref = db.collection('listings').document()
        listing_ref.set(listing_data)
        
        return jsonify({'message': 'Listing created!', 'listing_id': listing_ref.id})
        
    except Exception as e:
        print(f"Create listing error: {e}")
        return jsonify({'error': 'Something went wrong'})


# Get listings
@app.route('/get-listings', methods=['GET'])
def get_listings():
    try:
        listings_ref = db.collection('listings')
        query = listings_ref.where('status', '==', 'available')
        
        docs = query.stream()
        
        listings = []
        for doc in docs:
            listing_data = doc.to_dict()
            listing_data['listing_id'] = doc.id
            listing_data['latitude'] = float(listing_data.get('latitude', 22.3072))
            listing_data['longitude'] = float(listing_data.get('longitude', 73.1812))
            listings.append(listing_data)
        
        print(f"{len(listings)} available listings")
        
        return jsonify({'listings': listings})
        
    except Exception as e:
        print(f"Get listings error: {e}")
        return jsonify({'error': 'Failed to fetch listings'})


# Claim listing
@app.route('/claim-listing', methods=['POST'])
def claim_listing():
    data = request.get_json()
    
    listing_id = data.get('listing_id')
    ngo_user_id = data.get('ngo_user_id')
    
    if not listing_id or not ngo_user_id:
        return jsonify({'error': 'Missing required data'})
    
    try:
        user_doc = db.collection('users').document(ngo_user_id).get()
        
        if not user_doc.exists:
            return jsonify({'error': 'User not found. Please login.'})
        
        user_data = user_doc.to_dict()
        
        if user_data.get('user_type') != 'ngo':
            return jsonify({'error': 'Only NGOs can claim listings'})
        
        listing_ref = db.collection('listings').document(listing_id)
        listing_doc = listing_ref.get()
        
        if not listing_doc.exists:
            return jsonify({'error': 'Listing not found'})
        
        listing_data = listing_doc.to_dict()

        if listing_data.get('status') != 'available':
            return jsonify({'error': 'Listing already claimed'})
        
        listing_ref.update({
            'status': 'claimed', 
            'claimed_by': ngo_user_id, 
            'claimed_at': datetime.now().isoformat()
        })
        
        print(f"Listing {listing_id} claimed by {ngo_user_id}")
        
        return jsonify({'message': 'Listing claimed successfully'})
        
    except Exception as e:
        print(f"Claim listing error: {e}")
        return jsonify({'error': 'Failed to claim listing'})


# Complete listing
@app.route('/complete-listing', methods=['POST'])
def complete_listing():
    data = request.get_json()
    listing_id = data.get('listing_id')
    ngo_user_id = data.get('ngo_user_id')
    
    if not listing_id or not ngo_user_id:
        return jsonify({'error': 'Missing required data'})
    
    try:
        listing_ref = db.collection('listings').document(listing_id)
        listing_doc = listing_ref.get()
        
        if not listing_doc.exists:
            return jsonify({'error': 'Listing not found'})
        
        listing_data = listing_doc.to_dict()
        
        if listing_data.get('claimed_by') != ngo_user_id:
            return jsonify({'error': 'You did not claim this listing'})
        
        if listing_data.get('status') != 'claimed':
            return jsonify({'error': 'Listing not claimed'})
        
        listing_ref.update({
            'status': 'completed', 
            'completed_at': datetime.now().isoformat()
        })
        
        print(f"Listing {listing_id} completed by {ngo_user_id}")
        
        return jsonify({'message': 'Listing completed successfully'})
        
    except Exception as e:
        print(f"Complete listing error: {e}")
        return jsonify({'error': 'Failed to complete listing'})





# Upload image
@app.route('/upload-image', methods=['POST'])
def upload_image():
    # 1. Check if the file is in the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    try:
        # 2. ImgBB Configuration
        # REPLACE 'your_api_key_here' with your actual key
        api_key = 'b08ffd05a12bfdbc82cda7b9cc8a43d2' 
        api_url = "https://api.imgbb.com/1/upload"

        # 3. Prepare the image
        # ImgBB API usually expects the image as a Base64 string or a binary file
        # We will read the file and send it directly
        file_content = file.read()
        
        # 4. Make the request to ImgBB
        payload = {
            "key": api_key,
        }
        files = {
            "image": (file.filename, file_content)
        }

        response = requests.post(api_url, data=payload, files=files)
        res_data = response.json()

        # 5. Handle the ImgBB response
        if response.status_code == 200 and res_data['success']:
            # This is the direct link to the image
            image_url = res_data['data']['url']
            
            print(f"Successfully uploaded to ImgBB: {image_url}")
            
            return jsonify({
                'message': 'Image uploaded successfully',
                'image_url': image_url
            })
        else:
            print(f"ImgBB Error: {res_data}")
            return jsonify({'error': 'ImgBB upload failed'}), 500

    except Exception as e:
        print(f"Upload image error: {e}")
        return jsonify({'error': str(e)}), 500


# Cancel listing (NEW - for donor dashboard)
@app.route('/cancel-listing', methods=['POST'])
def cancel_listing():
    data = request.get_json()
    listing_id = data.get('listing_id')
    donor_id = data.get('donor_id')
    
    if not listing_id or not donor_id:
        return jsonify({'error': 'Missing required data'})
    
    try:
        listing_ref = db.collection('listings').document(listing_id)
        listing_doc = listing_ref.get()
        
        if not listing_doc.exists:
            return jsonify({'error': 'Listing not found'})
        
        listing_data = listing_doc.to_dict()
        
        if listing_data.get('donor_id') != donor_id:
            return jsonify({'error': 'You can only cancel your own listings'})
        
        if listing_data.get('status') != 'available':
            return jsonify({'error': 'Can only cancel available listings'})
        
        listing_ref.update({
            'status': 'cancelled', 
            'cancelled_at': datetime.now().isoformat()
        })
        
        print(f"Listing {listing_id} cancelled by {donor_id}")
        
        return jsonify({'message': 'Listing cancelled successfully'})
        
    except Exception as e:
        print(f"Cancel listing error: {e}")
        return jsonify({'error': 'Failed to cancel listing'})


# Submit feedback (NEW - for NGO feedback system)
@app.route('/submit-feedback', methods=['POST'])
def submit_feedback():
    data = request.get_json()
    listing_id = data.get('listing_id')
    ngo_user_id = data.get('ngo_user_id')
    feedback_type = data.get('feedback_type')  # 'up' or 'down'
    
    if not listing_id or not ngo_user_id or not feedback_type:
        return jsonify({'error': 'Missing required data'})
    
    try:
        listing_ref = db.collection('listings').document(listing_id)
        listing_doc = listing_ref.get()
        
        if not listing_doc.exists:
            return jsonify({'error': 'Listing not found'})
        
        listing_data = listing_doc.to_dict()
        donor_id = listing_data.get('donor_id')
        
        # Update donor reputation
        if donor_id:
            donor_ref = db.collection('users').document(donor_id)
            donor_doc = donor_ref.get()
            
            if donor_doc.exists:
                current_score = donor_doc.to_dict().get('reputation_score', 0)
                new_score = current_score + (1 if feedback_type == 'up' else -1)
                donor_ref.update({'reputation_score': new_score})
        
        # Store feedback
        listing_ref.update({
            'feedback': feedback_type,
            'feedback_by': ngo_user_id,
            'feedback_at': datetime.now().isoformat()
        })
        
        print(f"Feedback {feedback_type} submitted for listing {listing_id}")
        
        return jsonify({'message': 'Feedback submitted successfully'})
        
    except Exception as e:
        print(f"Submit feedback error: {e}")
        return jsonify({'error': 'Failed to submit feedback'})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    