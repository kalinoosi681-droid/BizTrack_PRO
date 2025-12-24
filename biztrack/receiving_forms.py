# ========================================
# biztrack/receiving_forms.py - NEW FILE
# Forms for Receiving System
# ========================================
from flask_wtf import FlaskForm
from wtforms import (
    StringField, IntegerField, FloatField, TextAreaField, 
    SubmitField, BooleanField, DateField, SelectField, HiddenField
)
from wtforms.validators import DataRequired, NumberRange, Optional, Length
from datetime import datetime


class ReceivingForm(FlaskForm):
    """Form for receiving stock"""
    
    # Product selection
    product_id = IntegerField(
        'Product ID', 
        validators=[DataRequired(message="Product is required")],
        render_kw={"readonly": True}
    )
    
    # Quantity
    quantity_received = IntegerField(
        'Quantity Received',
        validators=[
            DataRequired(message="Quantity is required"),
            NumberRange(min=1, message="Quantity must be at least 1")
        ],
        render_kw={"placeholder": "Enter quantity received"}
    )
    
    # Cost price
    cost_price = FloatField(
        'Cost Price (M)',
        validators=[
            DataRequired(message="Cost price is required"),
            NumberRange(min=0.01, message="Cost price must be greater than 0")
        ],
        render_kw={"placeholder": "0.00", "step": "0.01"}
    )
    
    # Calculated selling price (can be overridden)
    selling_price = FloatField(
        'Selling Price (M)',
        validators=[
            DataRequired(message="Selling price is required"),
            NumberRange(min=0.01, message="Selling price must be greater than 0")
        ],
        render_kw={"placeholder": "0.00", "step": "0.01"}
    )
    
    # Hidden field for margin
    margin_percent = HiddenField('Margin %')
    
    # Supplier info (optional)
    supplier_name = StringField(
        'Supplier Name',
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "Supplier name (optional)", "autocomplete": "off"}
    )
    
    supplier_phone = StringField(
        'Supplier Phone',
        validators=[Optional(), Length(max=20)],
        render_kw={"placeholder": "Supplier phone (optional)"}
    )
    
    # Invoice/Reference
    invoice_number = StringField(
        'Supplier Invoice #',
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Supplier invoice number (optional)"}
    )
    
    # Notes
    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "Additional notes (optional)", "rows": 3}
    )
    
    # Allow price override
    override_price = BooleanField('Override Calculated Price')
    
    submit = SubmitField('Receive Stock')


class BulkReceivingItemForm(FlaskForm):
    """Sub-form for bulk receiving line items"""
    product_id = IntegerField('Product ID', validators=[DataRequired()])
    quantity_received = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=1)])
    cost_price = FloatField('Cost Price', validators=[DataRequired(), NumberRange(min=0.01)])
    selling_price = FloatField('Selling Price', validators=[DataRequired(), NumberRange(min=0.01)])
    notes = StringField('Notes', validators=[Optional(), Length(max=200)])


class ReceivingFilterForm(FlaskForm):
    """Form for filtering receiving history"""
    start_date = DateField(
        'From Date',
        validators=[Optional()],
        format='%Y-%m-%d',
        render_kw={"type": "date"}
    )
    
    end_date = DateField(
        'To Date',
        validators=[Optional()],
        format='%Y-%m-%d',
        default=datetime.now,
        render_kw={"type": "date"}
    )
    
    product_id = IntegerField(
        'Product ID',
        validators=[Optional()],
        render_kw={"placeholder": "Filter by product ID"}
    )
    
    supplier_name = StringField(
        'Supplier',
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "Filter by supplier"}
    )
    
    submit = SubmitField('Apply Filters')


class CategoryMarginForm(FlaskForm):
    """Form for updating category profit margins"""
    category_name = StringField(
        'Category Name',
        validators=[DataRequired(), Length(max=100)],
        render_kw={"readonly": True}
    )
    
    profit_margin_percent = FloatField(
        'Profit Margin (%)',
        validators=[
            DataRequired(message="Margin percentage is required"),
            NumberRange(min=0, max=500, message="Margin must be between 0% and 500%")
        ],
        render_kw={"placeholder": "0.00", "step": "0.1"}
    )
    
    submit = SubmitField('Update Margin')


class OpeningStockForm(FlaskForm):
    """Form for recording opening stock (historical migration)"""
    product_id = IntegerField(
        'Product ID',
        validators=[DataRequired()],
        render_kw={"readonly": True}
    )
    
    quantity = IntegerField(
        'Opening Quantity',
        validators=[DataRequired(), NumberRange(min=0)],
        render_kw={"placeholder": "Current stock quantity"}
    )
    
    estimated_cost_price = FloatField(
        'Estimated Cost Price (M)',
        validators=[DataRequired(), NumberRange(min=0.01)],
        render_kw={"placeholder": "0.00", "step": "0.01"}
    )
    
    notes = TextAreaField(
        'Notes',
        validators=[Optional(), Length(max=500)],
        render_kw={"placeholder": "Opening stock migration notes", "rows": 2}
    )
    
    submit = SubmitField('Record Opening Stock')