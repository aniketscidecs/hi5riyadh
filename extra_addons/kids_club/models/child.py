from odoo import models, fields, api
from datetime import date
import base64
import io
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter


class Child(models.Model):
    _name = 'kids.child'
    _description = 'Child Information'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'

    # Basic Information
    name = fields.Char('Child Name', required=True, tracking=True)
    parent_id = fields.Many2one('res.partner', string='Parent', required=True, tracking=True)
    date_of_birth = fields.Date('Date of Birth', required=True, tracking=True)
    age = fields.Integer('Age', compute='_compute_age', store=True)
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female')
    ], string='Gender', tracking=True)
    
    # Image and Barcode
    image = fields.Binary('Photo', attachment=True)
    image_medium = fields.Binary('Medium-sized Photo', compute='_compute_image_medium', store=True)
    image_small = fields.Binary('Small-sized Photo', compute='_compute_image_small', store=True)
    
    # Barcode fields
    barcode_id = fields.Char('Barcode ID', required=True, copy=False, default=lambda self: self._generate_barcode_id())
    barcode_image = fields.Binary('Barcode Image', compute='_compute_barcode_image', store=True)
    
    # Additional Information
    emergency_contact = fields.Char('Emergency Contact')
    emergency_phone = fields.Char('Emergency Phone')
    medical_notes = fields.Text('Medical Notes')
    allergies = fields.Text('Allergies')
    
    # Status
    active = fields.Boolean('Active', default=True, tracking=True)
    registration_date = fields.Date('Registration Date', default=fields.Date.today, tracking=True)
    
    # Subscription Information
    subscription_ids = fields.One2many('kids.child.subscription', 'child_id', string='Subscriptions')
    current_subscription_id = fields.Many2one('kids.child.subscription', string='Current Subscription', 
                                            compute='_compute_current_subscription', store=True)
    subscription_count = fields.Integer('Subscription Count', compute='_compute_subscription_count')
    
    @api.model
    def _generate_barcode_id(self):
        """Generate unique barcode ID for child"""
        sequence = self.env['ir.sequence'].next_by_code('kids.child.barcode') or '0001'
        return f"KC{sequence}"
    
    @api.depends('date_of_birth')
    def _compute_age(self):
        """Calculate age from date of birth"""
        for record in self:
            if record.date_of_birth:
                today = date.today()
                record.age = today.year - record.date_of_birth.year - (
                    (today.month, today.day) < (record.date_of_birth.month, record.date_of_birth.day)
                )
            else:
                record.age = 0
    
    @api.depends('barcode_id')
    def _compute_barcode_image(self):
        """Generate barcode image"""
        for record in self:
            if record.barcode_id:
                try:
                    # Generate barcode using Code128
                    code128 = barcode.get_barcode_class('code128')
                    barcode_instance = code128(record.barcode_id, writer=ImageWriter())
                    
                    # Create image buffer
                    buffer = io.BytesIO()
                    barcode_instance.write(buffer)
                    buffer.seek(0)
                    
                    # Convert to base64
                    record.barcode_image = base64.b64encode(buffer.getvalue())
                except Exception:
                    record.barcode_image = False
            else:
                record.barcode_image = False
    
    @api.depends('image')
    def _compute_image_medium(self):
        """Compute medium sized image"""
        for record in self:
            if record.image:
                record.image_medium = self._resize_image(record.image, (128, 128))
            else:
                record.image_medium = False
    
    @api.depends('image')
    def _compute_image_small(self):
        """Compute small sized image"""
        for record in self:
            if record.image:
                record.image_small = self._resize_image(record.image, (64, 64))
            else:
                record.image_small = False
    
    def _resize_image(self, image_data, size):
        """Resize image to specified size"""
        try:
            image_stream = io.BytesIO(base64.b64decode(image_data))
            img = Image.open(image_stream)
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            output_stream = io.BytesIO()
            img.save(output_stream, format='PNG')
            output_stream.seek(0)
            
            return base64.b64encode(output_stream.getvalue())
        except Exception:
            return False
    
    @api.depends('subscription_ids')
    def _compute_subscription_count(self):
        for child in self:
            child.subscription_count = len(child.subscription_ids)
    
    @api.depends('subscription_ids', 'subscription_ids.state', 'subscription_ids.end_date')
    def _compute_current_subscription(self):
        for child in self:
            active_subscription = child.subscription_ids.filtered(
                lambda s: s.state == 'active' and s.start_date <= fields.Date.today() <= s.end_date
            )
            child.current_subscription_id = active_subscription[0] if active_subscription else False
    
    @api.model
    def create(self, vals):
        """Override create to ensure barcode_id is unique"""
        if not vals.get('barcode_id'):
            vals['barcode_id'] = self._generate_barcode_id()
        
        # Ensure barcode_id is unique
        while self.search([('barcode_id', '=', vals['barcode_id'])]):
            vals['barcode_id'] = self._generate_barcode_id()
        
        return super(Child, self).create(vals)
    
    @api.constrains('barcode_id')
    def _check_barcode_unique(self):
        """Ensure barcode_id is unique"""
        for record in self:
            if record.barcode_id:
                domain = [('barcode_id', '=', record.barcode_id), ('id', '!=', record.id)]
                if self.search_count(domain):
                    raise models.ValidationError(f"Barcode ID '{record.barcode_id}' already exists!")
    
    def action_view_subscriptions(self):
        """Action to view subscriptions for this child"""
        self.ensure_one()
        return {
            'name': f'Subscriptions for {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kids.child.subscription',
            'view_mode': 'list,form',
            'domain': [('child_id', '=', self.id)],
            'context': {
                'default_child_id': self.id,
                'search_default_child_id': self.id,
            },
            'target': 'current',
        }


class ChildSubscription(models.Model):
    _name = 'kids.child.subscription'
    _description = 'Child Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'start_date desc'
    
    child_id = fields.Many2one('kids.child', string='Child', required=True, ondelete='cascade')
    package_id = fields.Many2one('subscription.package', string='Package', required=True)
    start_date = fields.Date('Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date('End Date', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    
    # Pricing
    price = fields.Monetary('Price', compute='_compute_price', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self._get_default_currency())
    
    # Payment
    invoice_id = fields.Many2one('account.move', string='Invoice')
    payment_status = fields.Selection([
        ('unpaid', 'Unpaid'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid')
    ], string='Payment Status', default='unpaid')
    
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    
    @api.model
    def _get_default_currency(self):
        """Get default currency safely"""
        try:
            if self.env.company and self.env.company.currency_id:
                return self.env.company.currency_id.id
            else:
                # Fallback to USD if no company currency
                usd = self.env['res.currency'].search([('name', '=', 'USD')], limit=1)
                return usd.id if usd else 1
        except Exception:
            return 1
    
    @api.depends('package_id.price')
    def _compute_price(self):
        for record in self:
            record.price = record.package_id.price if record.package_id else 0.0
    
    @api.depends('child_id.name', 'package_id.name', 'start_date')
    def _compute_display_name(self):
        for record in self:
            child_name = record.child_id.name if record.child_id else 'Unknown Child'
            package_name = record.package_id.name if record.package_id else 'Unknown Package'
            start_date = record.start_date or 'No Date'
            record.display_name = f"{child_name} - {package_name} ({start_date})"
    
    @api.model
    def _cron_update_subscription_status(self):
        """Cron job to update subscription status based on dates"""
        today = fields.Date.today()
        
        # Activate subscriptions that should be active
        draft_subscriptions = self.search([
            ('state', '=', 'draft'),
            ('start_date', '<=', today)
        ])
        draft_subscriptions.write({'state': 'active'})
        
        # Expire subscriptions that have passed end date
        active_subscriptions = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today)
        ])
        active_subscriptions.write({'state': 'expired'})
    
    @api.model
    def fix_currency_references(self):
        """Fix any existing records with invalid currency references"""
        # Find subscriptions with invalid or missing currency_id
        subscriptions = self.search([('currency_id', '=', False)])
        if subscriptions:
            default_currency = self._get_default_currency()
            subscriptions.write({'currency_id': default_currency})
        
        # Also fix any records that might have invalid currency references
        all_subscriptions = self.search([])
        for subscription in all_subscriptions:
            try:
                # Try to access the currency_id to see if it's valid
                _ = subscription.currency_id.name
            except Exception:
                # If there's an error, fix it with default currency
                subscription.currency_id = self._get_default_currency()
