from unittest.mock import patch, MagicMock, ANY

from misc.extensions import ALREADY_ADDED, DB_ERROR, DB_SUCCESS
from misc.alchemy_db import AlchemyDb, Role, User

@patch("misc.alchemy_db.db.session")
@patch("misc.alchemy_db.User")
def test_add_user_success(mock_user, mock_session):
    svc = AlchemyDb()
    
    # No existing users
    mock_user.query.filter_by.return_value.first.return_value = None

    status, err = svc.addUser("alice", "alice@example.com", "pw123")

    assert status == DB_SUCCESS
    assert err is None

    # User object created
    mock_user.assert_called_with(
        name="alice",
        email="alice@example.com",
        password=ANY,   # use from unittest.mock import ANY
        role=Role.USER,
    )

    # Check DB actions
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@patch("misc.alchemy_db.db.session")
@patch("misc.alchemy_db.User")
def test_add_user_duplicate_email(mock_user, mock_session):
    svc = AlchemyDb()

    # Simulate existing user by email
    mock_user.query.filter_by.return_value.first.side_effect = [
        MagicMock(),  # when checking email
        None,         # when checking name
    ]

    status, err = svc.addUser("bob", "bob@example.com", "pw")

    assert status == ALREADY_ADDED
    assert err is None

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()

@patch("misc.alchemy_db.db.session")
@patch("misc.alchemy_db.User")
def test_add_user_duplicate_name(mock_user, mock_session, client):
    svc = AlchemyDb()

    # Simulate existing user by email
    mock_user.query.filter_by.return_value.first.side_effect = [
        None,         # when checking email
        MagicMock(),  # when checking name
    ]

    status, err = svc.addUser("bob", "bob@example.com", "pw")

    assert status == ALREADY_ADDED
    assert err is None

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()

@patch("misc.alchemy_db.db.session.rollback")    
@patch("misc.alchemy_db.db.session.commit")
def test_add_user_db_error(mock_commit, mock_rollback, client):
    svc = AlchemyDb()
    app = client.application

    # if mock is on session then User.query is not working well, because it also uses session ?
    mock_commit.side_effect=Exception("DB FAIL")
    with app.app_context():
        status, err = svc.addUser("alice2", "alice2@example.com", "secret123")

        assert status == DB_ERROR
        assert err is "DB FAIL"

        mock_rollback.assert_called()

def test_add_user_password_hashed(client):
    ''' Query DB and inspect user.password '''
    service = AlchemyDb()
    app = client.application

    with app.app_context():
        status, err = service.addUser("alice", "alice@example.com", "secret123")

        assert status == DB_SUCCESS
        user = User.query.filter_by(email="alice@example.com").first()

        assert user is not None
        assert user.password != "secret123"
        assert user.password.startswith("scrypt:32768")
    
def test_add_user_role(client):
    ''' Role defaults & custom role assignment '''
    service = AlchemyDb()
    app = client.application

    with app.app_context():
        service.addUser("alice", "alice@example.com", "secret123")

        user = User.query.filter_by(name="alice").first()

        assert user is not None
        assert user.role == Role.USER

def test_validate_user(client):
    service = AlchemyDb()
    app = client.application

    with app.app_context():
        service.addUser("alice", "alice@example.com", "secret123")

        user = service.validateUser("alice@example.com", "secret123")
        assert user is not None
        assert user.name == "alice"

def test_delete_user_success(client):
    service = AlchemyDb()
    app = client.application

    with app.app_context():
        service.addUser("alice", "alice@example.com", "secret123")

        user = service.getUserByMail("alice@example.com")
        assert user is not None

        status, msg = service.deleteUser(user.id)

        assert status == DB_SUCCESS
        assert msg == None

def test_delete_user_failure(client):
    service = AlchemyDb()
    app = client.application

    with app.app_context():
        status, msg = service.deleteUser(100)

        assert status == DB_ERROR
        assert msg == "NOT ADDED"

def test_get_users(client):
    service = AlchemyDb()
    app = client.application

    with app.app_context():
        service.addUser("alice", "alice@example.com", "secret123")
        service.addUser("bob", "bob@example.com", "secret123")

        users = service.getUsers()
        assert len(users) == 2