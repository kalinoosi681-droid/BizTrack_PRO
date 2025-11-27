
# ========================================
# FIX 2: forms.py - Fix PasswordField import
# ========================================

from flask_wtf import FlaskForm
from wtforms import (
    StringField, IntegerField, FloatField, SubmitField, 
    PasswordField, HiddenField, DateField, FormField, FieldList
)
from wtforms.validators import DataRequired, Email, NumberRange, Optional

# ----------------------------
# Authentication Forms
# ----------------------------
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])  # FIXED
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])  # FIXED
    role = StringField("Role", validators=[DataRequired()])
    submit = SubmitField("Register")

# ----------------------------
# Customer Forms
# ----------------------------
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
    
# ----------------------------
# Product Forms
# ----------------------------
class ProductAddForm(FlaskForm):
    action = HiddenField(default="add")
    name = StringField("Name", validators=[DataRequired()])
    category = StringField("Category", validators=[Optional()])
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Add Product")
    
class ProductUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Product ID", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    category = StringField("Category", validators=[Optional()])
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Update Product")

class ProductDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Product ID", validators=[DataRequired()])
    submit = SubmitField("Delete Product")

# ----------------------------
# Payroll Forms
# ----------------------------
class PayrollAddForm(FlaskForm):
    action = HiddenField(default="add")
    employee_name = StringField("Employee Name", validators=[DataRequired()])
    salary = FloatField("Salary", validators=[DataRequired(), NumberRange(min=0)])
    date = DateField("Date", validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField("Add Payroll")
    
class PayrollUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Payroll ID", validators=[DataRequired()])
    employee_name = StringField("Employee Name", validators=[DataRequired()])
    salary = FloatField("Salary", validators=[DataRequired(), NumberRange(min=0)])
    date = DateField("Date", validators=[DataRequired()], format='%Y-%m-%d')
    submit = SubmitField("Update Payroll")

class PayrollDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Payroll ID", validators=[DataRequired()])
    submit = SubmitField("Delete Payroll")

# ----------------------------
# Invoice Forms
# ----------------------------
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
    total = FloatField("Total", validators=[DataRequired()])
    date = StringField("Date", validators=[DataRequired()])
    submit = SubmitField("Update Invoice")

class InvoiceDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Invoice ID", validators=[DataRequired()])
    submit = SubmitField("Delete Invoice")

# ----------------------------