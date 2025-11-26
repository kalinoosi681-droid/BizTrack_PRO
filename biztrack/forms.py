from flask_wtf import FlaskForm
from wtforms import FormField, FieldList
from wtforms import StringField, IntegerField, FloatField, SubmitField
from wtforms import StringField, FloatField, IntegerField, DateField, HiddenField
from wtforms.validators import DataRequired, Email, NumberRange

# ----------------------------
# Customer Forms
# ----------------------------
class CustomerAddForm(FlaskForm):
    action = HiddenField(default="add")
    name = StringField("Name", validators=[DataRequired()])
    phone = StringField("Phone")
    email = StringField("Email", validators=[Email()])
    submit = SubmitField("Add Customer")
    
class CustomerUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Customer ID", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    phone = StringField("Phone")
    email = StringField("Email")
    submit = SubmitField("Update Customer")

class CustomerDeleteForm(FlaskForm):
    id = IntegerField("Customer ID", validators=[DataRequired()])
    submit = SubmitField("Delete Customer")
    
# ----------------------------
# Payroll Forms
# ----------------------------
class PayrollAddForm(FlaskForm):
    action = HiddenField(default="add")
    employee_name = StringField("Employee Name", validators=[DataRequired()])
    salary = FloatField("Salary", validators=[DataRequired(), NumberRange(min=0)])
    date = DateField("Date", validators=[DataRequired()])
    submit = SubmitField("Add Payroll")

class PayrollDeleteForm(FlaskForm):
    action = HiddenField(default="delete")
    id = IntegerField("Payroll ID", validators=[DataRequired()])
    submit = SubmitField("Delete Payroll")

# ----------------------------
# Product Forms
# ----------------------------
class ProductAddForm(FlaskForm):
    action = HiddenField(default="add")
    name = StringField("Name", validators=[DataRequired()])
    category = StringField("Category")
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Add Product")
    
class ProductUpdateForm(FlaskForm):
    action = HiddenField(default="update")
    id = IntegerField("Product ID", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    category = StringField("Category")
    qty = IntegerField("Quantity", validators=[DataRequired()])
    price = FloatField("Price", validators=[DataRequired()])
    submit = SubmitField("Update Product")

class ProductDeleteForm(FlaskForm):
    id = IntegerField("Product ID", validators=[DataRequired()])
    submit = SubmitField("Delete Product")

# ----------------------------
# Invoice Forms
# ----------------------------
class ItemForm(FlaskForm):
    pid = IntegerField("Product ID", validators=[DataRequired()])
    qty = IntegerField("Quantity", validators=[DataRequired()])
    price = FloatField("Price", validators=[DataRequired()])

class InvoiceAddForm(FlaskForm):
    action = HiddenField(default="add")
    customer_id = IntegerField("Customer ID", validators=[DataRequired()])
    items = FieldList(FormField(ItemForm), min_entries=1)
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
# Authentication Forms
# ----------------------------
class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = StringField("Password", validators=[DataRequired()])
    submit = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = StringField("Password", validators=[DataRequired()])
    role = StringField("Role", validators=[DataRequired()])
    submit = SubmitField("Register")