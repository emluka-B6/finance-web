from unittest.mock import patch, MagicMock

def test_register_success(client):
    response = client.post(
        "/register",
        data={
            "name": "alice",
            "email": "alice@gmail.com",
            "password": "pass123",
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"User added successfully!" in response.data
    

def test_register_already_added(client):
    def post_alice(client):
        response = client.post(
            "/register",
            data={
                "name": "alice",
                "email": "alice@gmail.com",
                "password": "pass123",
            },
            follow_redirects=True
        )
        return response
    post_alice(client)
    response = post_alice(client)

    assert response.status_code == 200
    assert b"User already added!" in response.data


def test_register_of_invalid_mail(client):
    response = client.post(
        "/register",
        data={
            "name": "alice",
            "email": "alice@example.com", #invalid domain
            "password": "pass123",
        },
        follow_redirects=True
    )

    assert response.status_code == 200
    assert b"Error: Invalid email address -" in response.data


def test_register_with_missing_input(client):
    response = client.post(
        "/register", data={ "email": "alice@gmail.com", "password": "pass123"},
        follow_redirects=True
    )
    assert b"Error: All fields are required" in response.data
    response = client.post(
        "/register", data={"name": "alice",  "password": "pass123"},
        follow_redirects=True
    )
    assert b"Error: All fields are required" in response.data
    response = client.post(
        "/register", data={"name": "alice", "email": "alice@gmail.com"},
        follow_redirects=True
    )
    assert b"Error: All fields are required" in response.data

def test_login_with_missing_input(client):
    response = client.post(
        "/login", data={"email": "alice@gmail.com"},
        follow_redirects=True
    )
    assert b"Error: Both email and password are required" in response.data
    response = client.post(
        "/login", data={"password": "pass123"},
        follow_redirects=True
    )
    assert b"Error: Both email and password are required" in response.data

@patch("user.dbApi.validateUser")
def test_login_with_invalid_data(mock_validate, client):
    mock_validate.return_value = None

    response = client.post(
        "/login", data={"email": "alice@gmail.com", "password": "pass123"},
        follow_redirects=True
    )

    mock_validate.assert_called_once()
    assert response.status_code == 200
    assert b"Error: Invalid email or password" in response.data


def test_login_successful(client):
    client.post(
        "/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"},
    )
    response = client.post(
        "/login", data={"email": "alice@gmail.com", "password": "pass123"},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Register" not in response.data
    assert b"Login" not in response.data
    assert b"Logout" in response.data
    assert b"General Market News" in response.data 


def test_logout_successful(client):
    client.post(
        "/register", data={"name": "alice", "email": "alice@gmail.com", "password": "pass123"}
    )
    client.post(
        "/login", data={"email": "alice@gmail.com", "password": "pass123"}
    )
    response = client.get(
        "/logout", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Register" in response.data
    assert b"Login" in response.data
    # assert b"Logout" not in response.data
    assert b"Success: You have been logged out" in response.data

from misc.alchemy_db import AlchemyDb, Role
from misc.extensions import ALREADY_ADDED, DB_ERROR, DB_SUCCESS

def test_delete_is_failing(client):
    svc = AlchemyDb()
    app = client.application

    with app.app_context():
        status, err = svc.addUser("alice", "alice@gmail.com", "pw123")
        assert status == DB_SUCCESS
        status, err = svc.addUser("bob", "bob@gmail.com", "pw123", Role.ADMIN)  
        assert status == DB_SUCCESS

    response = client.post(
        "/login", data={"email": "bob@gmail.com", "password": "pw123"}
    )
    response = client.post(
        f"/delete/0", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"An error occurred:" in response.data

def test_delete_successful(client):
    svc = AlchemyDb()
    app = client.application

    with app.app_context():
        status, err = svc.addUser("alice", "alice@gmail.com", "pw123")
        assert status == DB_SUCCESS
        status, err = svc.addUser("bob", "bob@gmail.com", "pw123", Role.ADMIN)  
        assert status == DB_SUCCESS
        alice_id = svc.getUserByMail("alice@gmail.com").id

    response = client.post(
        "/login", data={"email": "bob@gmail.com", "password": "pw123"}
    )
    response = client.post(
        f"/delete/{alice_id}", follow_redirects=True
    )
    assert response.status_code == 200
    assert b"User deleted successfully!" in response.data