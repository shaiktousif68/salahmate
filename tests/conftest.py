import pytest
from app import create_app, db
from app.models.user import User


@pytest.fixture
def app():
    """Create a test application."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def user_data():
    """Provides a dictionary of test user data."""
    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'password123',
        'confirm_password': 'password123',
        'full_name': 'Test User'
    }


@pytest.fixture
def auth_client(client, user_data):
    """Create an authenticated test client."""
    # Register a user
    client.post('/register', data=user_data)

    # Login
    client.post('/login', data={
        'username': user_data['username'],
        'password': user_data['password']
    }, follow_redirects=True)

    return client