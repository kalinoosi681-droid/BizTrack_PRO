
# ========================================
# FILE 2: biztrack/forms.py (COMPLETE WITH UPDATE FORMS)
# ========================================

from flask import flash
from flask_wtf import FlaskForm
from wtforms import (BooleanField, 
    StringField, IntegerField, FloatField, SubmitField, SelectField,
    PasswordField, HiddenField, DateField, FormField, FieldList
)
from wtforms.validators import DataRequired, Email, NumberRange, Optional, Length, EqualTo, ValidationError
from datetime import datetime
from .biztrack_db import get_user_by_username, execute_query

# Authentication Forms
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember = BooleanField("Remember Me")
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=4, max=25)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters long.")])
    password2 = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo('password', message="Passwords must match.")])
    submit = SubmitField("Register")

    def validate_username(self, username):
        """Check if username already exists."""
        if get_user_by_username(username.data):
            raise ValidationError("Username already exists. Please choose a different one.")

class ForgotPasswordForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    submit = SubmitField("Request Password Reset")

class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8, message="Password must be at least 8 characters long.")])
    password2 = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo('password', message="Passwords must match.")])
    submit = SubmitField("Reset Password")


# Customer Forms
class CustomerAddForm(FlaskForm):
    action = HiddenField(default="add")
    name = StringField("Name", validators=[DataRequired()])
    phone = StringField("Phone", validators=[Optional()])
    email = StringField("Email", validators=[Optional(), Email()])
    submit = SubmitField("Add Customer")
    
class CustomerUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Customer ID", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    phone = StringField("Phone", validators=[Optional()])
    email = StringField("Email", validators=[Optional(), Email()])
    submit = SubmitField("Update Customer")

class CustomerDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Customer ID", validators=[DataRequired()])
    submit = SubmitField("Delete Customer")

# Product Forms
class ProductAddForm(FlaskForm):
    action = HiddenField(default="add")
    name = StringField("Name", validators=[DataRequired(), Length(min=3, max=100)])
    category = StringField("Category", validators=[Optional()])
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Add Product")

    def validate_name(self, name):
        """Check if product with same name and category already exists."""
        category = self.category.data or ""
        exists = execute_query(
            "SELECT id FROM products WHERE LOWER(name) = ? AND LOWER(COALESCE(category, '')) = ?;",
            (name.data.lower(), category.lower()), fetchone=True)
        if exists:
            raise ValidationError(f"A product named '{name.data}' already exists in the '{category}' category.")
    
class ProductUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Product ID", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired(), Length(min=3, max=100)])
    category = StringField("Category", validators=[Optional()])
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Update Product")

class ProductDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Product ID", validators=[DataRequired()])
    submit = SubmitField("Delete Product")

class ProductThresholdUpdateForm(FlaskForm):
    """Form to update only the low stock threshold."""
    action = HiddenField(default="update_threshold")
    id = IntegerField("Product ID", validators=[DataRequired()])
    low_stock_threshold = IntegerField("Low Stock Threshold", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Update Threshold")

# New form for bulk product actions
class ProductBulkUpdateForm(FlaskForm):
    """Form for handling bulk product updates."""
    product_ids = FieldList(HiddenField(), min_entries=1)
    bulk_action = SelectField("Action", choices=[('set_category', 'Set Category'), ('adjust_price', 'Adjust Price by %')], validators=[DataRequired()])
    new_category = StringField("New Category", validators=[Optional(), Length(max=100)])
    price_percentage = FloatField("Price Adjustment (%)", validators=[Optional(), NumberRange(min=-90, max=200)])
    submit = SubmitField("Apply Bulk Action")

# Payroll Forms
class PayrollAddForm(FlaskForm):
    action = HiddenField(default="add")
    employee_name = StringField("Employee Name", validators=[DataRequired(), Length(min=3, max=100)])
    salary = FloatField("Salary", validators=[DataRequired(), NumberRange(min=0)])
    date = DateField("Date", validators=[DataRequired()], format='%Y-%m-%d', default=datetime.now)
    submit = SubmitField("Add Payroll")

class PayrollUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Payroll ID", validators=[DataRequired()])
    employee_name = StringField("Employee Name", validators=[DataRequired(), Length(min=3, max=100)])
    salary = FloatField("Salary", validators=[DataRequired(), NumberRange(min=0)], default=0.0)
    date = DateField("Date", validators=[DataRequired()], format='%Y-%m-%d', default=datetime.now)
    submit = SubmitField("Update Payroll")

class PayrollDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Payroll ID", validators=[DataRequired()])
    submit = SubmitField("Delete Payroll")

# Invoice Forms
class ItemForm(FlaskForm):
    pid = IntegerField("Product ID", validators=[DataRequired()])
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=1)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])

class InvoiceAddForm(FlaskForm):
    action = HiddenField(default="add")
    customer_id = IntegerField("Customer ID", validators=[DataRequired()])
    items = FieldList(FormField(ItemForm), min_entries=1, max_entries=10)
    submit = SubmitField("Create Invoice")
    
class InvoiceUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Invoice ID", validators=[DataRequired()])
    customer_id = IntegerField("Customer ID", validators=[DataRequired()])
    total = FloatField("Total", validators=[DataRequired()], default=0.0)
    date = DateField("Date", validators=[DataRequired()], format='%Y-%m-%d', default=datetime.now())
    submit = SubmitField("Update Invoice")

class InvoiceDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Invoice ID", validators=[DataRequired()])
    submit = SubmitField("Delete Invoice")