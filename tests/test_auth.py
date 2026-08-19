import json


def test_register_page(client):
    """Test that the register page loads."""
    response = client.get('/register')
    assert response.status_code == 200


def test_register_success(client, user_data):
    """Test successful user registration."""
    response = client.post('/register', data=user_data, follow_redirects=True)

    assert response.status_code == 200
    assert b'Registration successful! Please log in.' in response.data


def test_register_duplicate_username(client, user_data):
    """Test registration with duplicate username."""
    # Create a user first
    client.post('/register', data=user_data)

    # Try to register with same username
    response = client.post('/register', data={
        'username': user_data['username'],
        'email': 'other@example.com',
        'password': user_data['password'],
        'confirm_password': user_data['confirm_password'],
        'full_name': 'Other User'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Username already exists.' in response.data


def test_register_password_mismatch(client, user_data):
    """Test registration with mismatched passwords."""
    response = client.post('/register', data={
        'username': 'mismatchuser',
        'email': 'mismatch@example.com',
        'password': user_data['password'],
        'confirm_password': 'different123'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Passwords do not match.' in response.data


def test_login_page(client):
    """Test that the login page loads."""
    response = client.get('/login')
    assert response.status_code == 200


def test_login_success(client, user_data):
    """Test successful login."""
    # Register a user
    client.post('/register', data=user_data)

    # Login
    response = client.post('/login', data={
        'username': user_data['username'],
        'password': user_data['password']
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Welcome back' in response.data


def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post('/login', data={
        'username': 'nonexistent',
        'password': 'wrongpassword'
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b'Invalid username/email or password.' in response.data


def test_logout(auth_client):
    """Test logout."""
    # The auth_client fixture provides a logged-in client
    response = auth_client.get('/logout', follow_redirects=True)

    assert response.status_code == 200
    assert b'You have been logged out.' in response.data