from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import pickle
import os
import logging

# Import our generator
from trajectory_generator import TimeAwareAStarGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configure CORS to allow Vercel frontend
CORS(app, resources={
    r"/api/*": {
        "origins": [
            "https://surveillanceware-app.vercel.app",
            "http://localhost:5173"
        ],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Global generator instance
generator = None

def load_models():
    """Load pre-trained models on startup"""
    global generator
    
    logger.info("Loading trajectory models...")
    
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    
    try:
        # Load transition matrices
        with open(os.path.join(models_dir, 'user_transition_probabilities.pkl'), 'rb') as f:
            user_transitions = pickle.load(f)
        
        with open(os.path.join(models_dir, 'global_transition_probabilities.pkl'), 'rb') as f:
            global_transitions = pickle.load(f)
        
        with open(os.path.join(models_dir, 'state_space.pkl'), 'rb') as f:
            state_space = pickle.load(f)
        
        # Initial distribution (optional, can be None)
        initial_dist_path = os.path.join(models_dir, 'initial_distribution.pkl')
        if os.path.exists(initial_dist_path):
            with open(initial_dist_path, 'rb') as f:
                initial_distribution = pickle.load(f)
        else:
            initial_distribution = None
        
        # Initialize generator
        generator = TimeAwareAStarGenerator(
            user_transitions=user_transitions,
            global_transitions=global_transitions,
            initial_distribution=initial_distribution,
            state_space=state_space
        )
        
        logger.info(f"✓ Models loaded successfully!")
        logger.info(f"  Users: {len(user_transitions)}")
        logger.info(f"  Global states: {len(global_transitions)}")
        
    except FileNotFoundError as e:
        logger.error(f"❌ Model files not found: {e}")
        logger.error("Place your .pkl files in backend/models/ directory")
        raise
    except Exception as e:
        logger.error(f"❌ Error loading models: {e}")
        raise

@app.route('/api/users', methods=['GET'])
def get_users():
    """Get list of available users"""
    try:
        if generator is None:
            return jsonify({'error': 'Models not loaded'}), 500
        
        users = sorted(list(generator.user_transitions.keys()))
        
        logger.info(f"Returning {len(users)} available users")
        
        return jsonify({
            'users': users,
            'total': len(users)
        })
        
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/predict-trajectory', methods=['POST'])
def predict_trajectory():
    """Generate trajectory prediction"""
    try:
        data = request.get_json()
        
        # Parse input
        start_lat = float(data['start_lat'])
        start_lon = float(data['start_lon'])
        end_lat = float(data['end_lat'])
        end_lon = float(data['end_lon'])
        start_time = datetime.fromisoformat(data['start_time'])
        end_time = datetime.fromisoformat(data['end_time'])
        
        # Get user_id from request
        user_id = data.get('user_id')
        
        if user_id is not None:
            user_id = int(user_id)
            
            # Validate user exists
            if user_id not in generator.user_transitions:
                available_users = list(generator.user_transitions.keys())
                return jsonify({
                    'error': f'User {user_id} not found',
                    'message': f'Available users: {available_users[:10]}...',
                    'available_users': available_users
                }), 404
        else:
            # Use first user if none specified
            user_id = list(generator.user_transitions.keys())[17]
            logger.info(f"No user_id provided, using default user: {user_id}")
        
        # Generate trajectory
        logger.info(f"Generating trajectory for user {user_id}")
        logger.info(f"  From: ({start_lat}, {start_lon}) at {start_time}")
        logger.info(f"  To: ({end_lat}, {end_lon}) at {end_time}")
        
        result = generator.generate_trajectory(
            start_lat=start_lat,
            start_lon=start_lon,
            end_lat=end_lat,
            end_lon=end_lon,
            start_time=start_time,
            end_time=end_time,
            user_id=user_id
        )
        
        # Add user_id to response
        result['user_id'] = user_id
        
        logger.info(f"✓ Generated {result['metadata']['num_points']} points")
        logger.info(f"✓ Confidence: {result['confidence']['level']} ({result['confidence']['score']:.1%})")
        
        return jsonify(result)
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return jsonify({'error': str(e), 'message': 'Invalid input data'}), 400
    except Exception as e:
        logger.error(f"Error generating trajectory: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e), 'message': 'Server error'}), 500

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'models_loaded': generator is not None,
        'users_available': len(generator.user_transitions) if generator else 0
    })


load_models()

if __name__ == '__main__':
    # Only runs when testing locally
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

