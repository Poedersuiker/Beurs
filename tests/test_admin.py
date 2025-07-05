import unittest
from unittest.mock import patch, MagicMock
from flask import Flask
from app.routes import main_bp  # Assuming your blueprint is named main_bp
from app import db  # Assuming your db object is initialized in app/__init__.py
from app import create_app # Import create_app

class AdminTestCase(unittest.TestCase):

    def setUp(self):
        """Set up test variables."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:' # Use in-memory SQLite for tests
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all() # Create tables for the in-memory database

    def tearDown(self):
        """Tear down test variables."""
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @patch('app.routes.db', new_callable=MagicMock)
    def test_admin_page_db_connection_success(self, mock_db):
        """Test the admin page when the database connection is successful."""
        # Mock the db.session.execute to simulate a successful connection
        mock_db.session.execute.return_value = None  # Or some expected result if necessary

        with self.app.test_client() as client:
            response = client.get('/admin')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Successfully connected to the database.", response.data)
            mock_db.session.execute.assert_called_once_with('SELECT 1')

    @patch('app.routes.db')
    def test_admin_page_db_connection_failure(self, mock_db):
        """Test the admin page when the database connection fails."""
        # Mock the db.session.execute to raise an SQLAlchemyError
        from sqlalchemy.exc import SQLAlchemyError
        mock_db.session.execute.side_effect = SQLAlchemyError("Database connection failed")

        with self.app.test_client() as client:
            response = client.get('/admin')
            self.assertEqual(response.status_code, 200) # The page should still load
            self.assertIn(b"Failed to connect to the database: Database connection failed", response.data)
            mock_db.session.execute.assert_called_once_with('SELECT 1')

if __name__ == '__main__':
    unittest.main()
