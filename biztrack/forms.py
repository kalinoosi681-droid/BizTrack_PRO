from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, SubmitField
from wtforms.validators import DataRequired, Email, NumberRange

# ----------------------------
# Customer Forms
# ----------------------------
class CustomerAddForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    phone = StringField("Phone")
    email = StringField("Email", validators=[Email()])
    submit = SubmitField("Add Customer")

class CustomerDeleteForm(FlaskForm):
    id = IntegerField("Customer ID", validators=[DataRequired()])
    submit = SubmitField("Delete Customer")

# ----------------------------
# Product Forms
# ----------------------------
class ProductAddForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    category = StringField("Category")
    qty = IntegerField("Quantity", validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField("Price", validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField("Add Product")

class ProductDeleteForm(FlaskForm):
    id = IntegerField("Product ID", validators=[DataRequired()])
    submit = SubmitField("Delete Product")

# ----------------------------
# Invoice Forms
# ----------------------------
class InvoiceAddForm(FlaskForm):
    customer_id = IntegerField("Customer ID", validators=[DataRequired()])
    # items will be handled via JSON or dynamic UI, so not a direct field here
    submit = SubmitField("Create Invoice")

class InvoiceDeleteForm(FlaskForm):
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