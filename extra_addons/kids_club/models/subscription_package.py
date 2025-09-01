from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SubscriptionPackage(models.Model):
    _name = 'subscription.package'
    _description = 'Subscription Package'
    _order = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Package Name (English)',
        required=True,
        tracking=True,
        help='Name of the subscription package in English'
    )
    
    name_arabic = fields.Char(
        string='Package Name (Arabic)',
        help='Name of the subscription package in Arabic'
    )
    
    price = fields.Monetary(
        string='Sales Price',
        required=True,
        tracking=True,
        help='Price of the subscription package'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency for the package price'
    )
    
    linked_product_id = fields.Many2one(
        'product.product',
        string='Linked Product',
        readonly=True,
        help='Automatically created service product linked to this package'
    )
    
    description = fields.Text(
        string='Description',
        help='Optional description of the package'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        tracking=True,
        help='If unchecked, it will allow you to hide the package without removing it'
    )
    
    # Package Image
    image = fields.Image(
        string='Package Image',
        help='Upload an image for this subscription package'
    )
    
    # Visit and Duration Fields
    number_of_visits = fields.Integer(
        string='Number of Visits',
        default=1,
        tracking=True,
        help='Maximum number of visits allowed with this package'
    )
    
    validity_period = fields.Selection([
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Days')
    ], string='Validity Period', default='monthly', required=True, tracking=True,
       help='Select the validity period for this package')
    
    validity_days = fields.Integer(
        string='Validity (Days)',
        compute='_compute_validity_days',
        store=True,
        tracking=True,
        help='Number of days this package is valid (auto-calculated based on period)'
    )
    
    custom_validity_days = fields.Integer(
        string='Custom Validity Days',
        default=30,
        tracking=True,
        help='Custom number of validity days (only used when validity period is custom)'
    )
    
    # Branch/Company Field
    company_id = fields.Many2one(
        'res.company',
        string='Branch/Company',
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
        help='Branch or company where this package is available'
    )
    
    # Time Allowance Fields
    daily_free_minutes = fields.Integer(
        string='Daily Free Minutes',
        default=0,
        tracking=True,
        help='Number of free minutes allowed per day'
    )
    
    margin_minutes = fields.Integer(
        string='Margin Minutes',
        default=0,
        tracking=True,
        help='Additional buffer time in minutes'
    )
    
    # Extra Time Pricing (Simplified)
    extra_time_charge_per_minute = fields.Monetary(
        string='Extra Time Charge (per minute)',
        default=5.0,
        tracking=True,
        help='Charge per minute for time beyond daily free minutes + margin minutes'
    )

    @api.model
    def create(self, vals):
        """Override create to automatically generate linked service product"""
        # Create the package first
        package = super().create(vals)
        
        # Create the linked service product
        product_vals = {
            'name': package.name,
            'type': 'service',
            'list_price': package.price,
            'sale_ok': True,
            'purchase_ok': False,
            'categ_id': self._get_service_category_id(),
        }
        
        product = self.env['product.product'].create(product_vals)
        
        # Link the product to the package
        package.linked_product_id = product.id
        
        return package

    def write(self, vals):
        """Override write to sync changes with linked product"""
        result = super().write(vals)
        
        # Check if name or price changed
        if 'name' in vals or 'price' in vals:
            for package in self:
                if package.linked_product_id:
                    product_vals = {}
                    if 'name' in vals:
                        product_vals['name'] = package.name
                    if 'price' in vals:
                        product_vals['list_price'] = package.price
                    
                    package.linked_product_id.write(product_vals)
        
        # Handle active/inactive sync
        if 'active' in vals:
            for package in self:
                if package.linked_product_id:
                    package.linked_product_id.active = package.active
        
        return result

    def unlink(self):
        """Override unlink to delete linked products"""
        # Store linked products before deletion
        linked_products = self.mapped('linked_product_id').filtered(lambda p: p.exists())
        
        # Delete the packages
        result = super().unlink()
        
        # Delete the linked products
        if linked_products:
            linked_products.unlink()
        
        return result

    def toggle_active(self):
        """Toggle active state and sync with linked product"""
        for package in self:
            package.active = not package.active
            if package.linked_product_id:
                package.linked_product_id.active = package.active

    def _get_service_category_id(self):
        """Get or create a service category for subscription packages"""
        category = self.env['product.category'].search([
            ('name', '=', 'Subscription Services')
        ], limit=1)
        
        if not category:
            category = self.env['product.category'].create({
                'name': 'Subscription Services',
                'parent_id': False,
            })
        
        return category.id

    @api.constrains('price')
    def _check_price(self):
        """Validate that price is positive"""
        for package in self:
            if package.price <= 0:
                raise ValidationError("Package price must be greater than zero.")

    @api.depends('validity_period', 'custom_validity_days')
    def _compute_validity_days(self):
        """Compute the number of validity days based on selected period"""
        for package in self:
            if package.validity_period == 'weekly':
                package.validity_days = 7
            elif package.validity_period == 'monthly':
                package.validity_days = 30
            elif package.validity_period == 'yearly':
                package.validity_days = 365
            elif package.validity_period == 'custom':
                package.validity_days = package.custom_validity_days or 30
            else:
                package.validity_days = 30  # Default fallback

    @api.constrains('name')
    def _check_name(self):
        """Validate that name is not empty"""
        for package in self:
            if not package.name or not package.name.strip():
                raise ValidationError("Package name cannot be empty.")
    
    @api.constrains('custom_validity_days')
    def _check_custom_validity_days(self):
        """Validate that custom validity days is positive"""
        for package in self:
            if package.validity_period == 'custom' and package.custom_validity_days <= 0:
                raise ValidationError("Custom validity days must be greater than zero.")
    
    @api.constrains('number_of_visits')
    def _check_visits(self):
        """Validate that number of visits is positive"""
        for package in self:
            if package.number_of_visits <= 0:
                raise ValidationError("Number of visits must be greater than zero.")
    
    @api.constrains('daily_free_minutes', 'margin_minutes')
    def _check_minutes(self):
        """Validate that time fields are non-negative"""
        for package in self:
            if package.daily_free_minutes < 0:
                raise ValidationError("Daily free minutes cannot be negative.")
            if package.margin_minutes < 0:
                raise ValidationError("Margin minutes cannot be negative.")
    
    @api.constrains('extra_time_charge_per_minute')
    def _check_extra_time_charge(self):
        """Validate that extra time charge per minute is non-negative"""
        for package in self:
            if package.extra_time_charge_per_minute < 0:
                raise ValidationError("Extra time charge per minute cannot be negative.")

    def action_view_linked_product(self):
        """Action to view the linked product"""
        self.ensure_one()
        if not self.linked_product_id:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Linked Product',
            'res_model': 'product.product',
            'res_id': self.linked_product_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
