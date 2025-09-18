from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta, date
import uuid
import json
import time
import base64
import io
from PIL import Image, ImageDraw, ImageFont
import barcode
from barcode.writer import ImageWriter


class Child(models.Model):
    _name = 'kids.child'
    _description = 'Child'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'name'
    
    _sql_constraints = [
        ('barcode_id_unique', 'UNIQUE(barcode_id)', 'Barcode ID must be unique for each child!'),
    ]

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
    
    # Check-in/Check-out Information
    checkin_ids = fields.One2many('kids.child.checkin', 'child_id', string='Check-ins')
    is_checked_in = fields.Boolean('Currently Checked In', compute='_compute_checkin_status')
    current_checkin_id = fields.Many2one('kids.child.checkin', string='Current Check-in', 
                                        compute='_compute_checkin_status')
    
    @api.model
    def _generate_barcode_id(self):
        """Generate unique barcode ID for child"""
        # Try to generate a unique barcode ID
        max_attempts = 100
        for attempt in range(max_attempts):
            sequence = self.env['ir.sequence'].next_by_code('kids.child.barcode') or '0001'
            barcode_id = f"KC{sequence}"
            
            # Check if this barcode already exists
            existing = self.search([('barcode_id', '=', barcode_id)], limit=1)
            if not existing:
                return barcode_id
        
        # If we couldn't generate a unique ID after max attempts, raise an error
        raise ValidationError("Unable to generate a unique barcode ID. Please contact administrator.")
    
    @api.constrains('barcode_id')
    def _check_barcode_uniqueness(self):
        """Ensure barcode ID is unique"""
        for record in self:
            if record.barcode_id:
                duplicate = self.search([
                    ('barcode_id', '=', record.barcode_id),
                    ('id', '!=', record.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(f"Barcode ID '{record.barcode_id}' already exists for child '{duplicate.name}'. Each child must have a unique barcode ID.")
    
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
        for record in self:
            record.subscription_count = len(record.subscription_ids)
    
    @api.depends('checkin_ids.checkout_time', 'checkin_ids.state')
    def _compute_checkin_status(self):
        """Compute if child is currently checked in"""
        for record in self:
            # Find active check-in: either checked_in or pending_checkout_otp states
            current_checkin = record.checkin_ids.filtered(
                lambda c: not c.checkout_time and c.state in ['checked_in', 'pending_checkout_otp']
            )
            if current_checkin:
                record.is_checked_in = True
                record.current_checkin_id = current_checkin[0]
            else:
                record.is_checked_in = False
                record.current_checkin_id = False
    
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
    
    def action_quick_checkout(self):
        """Quick checkout for currently checked-in child"""
        self.ensure_one()
        
        # Find active check-in (including those in checkout OTP pending state)
        active_checkin = self.env['kids.child.checkin'].search([
            ('child_id', '=', self.id),
            ('state', 'in', ['checked_in', 'pending_checkout_otp'])
        ], limit=1)
        
        if not active_checkin:
            raise ValidationError("Child is not currently checked in.")
        
        # Always open the checkout wizard - let the wizard handle pending OTP states internally
        return {
            'type': 'ir.actions.act_window',
            'name': 'Checkout',
            'res_model': 'kids.checkout.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_child_id': self.id,
            },
        }
    
    def action_view_checkins(self):
        """Action to view check-ins for this child"""
        self.ensure_one()
        return {
            'name': f'Check-ins for {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kids.child.checkin',
            'view_mode': 'list,form',
            'domain': [('child_id', '=', self.id)],
            'context': {
                'default_child_id': self.id,
                'search_default_child_id': self.id,
            },
            'target': 'current',
        }
    
    def action_open_checkin_wizard(self):
        """Open quick check-in wizard for this child"""
        self.ensure_one()
        
        # Always open the wizard - let the wizard handle pending OTP states internally
        return {
            'name': 'Quick Check-in',
            'type': 'ir.actions.act_window',
            'res_model': 'kids.checkin.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_child_id': self.id,
            },
        }
    
    def action_bulk_checkin(self):
        """Bulk check-in for multiple selected children"""
        # Filter only children that can be checked in (not already checked in and active)
        eligible_children = self.filtered(lambda c: not c.is_checked_in and c.active)
        
        if not eligible_children:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Children Available',
                    'message': 'No eligible children selected for check-in. Children must be active and not already checked in.',
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # If only one child, open individual check-in wizard
        if len(eligible_children) == 1:
            return eligible_children.action_open_checkin_wizard()
        
        # For multiple children, open bulk check-in wizard
        return {
            'name': 'Bulk Check-in',
            'type': 'ir.actions.act_window',
            'res_model': 'kids.bulk.checkin.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_child_ids': [(6, 0, eligible_children.ids)],
                'active_ids': eligible_children.ids,
            },
        }


class ChildSubscription(models.Model):
    _name = 'kids.child.subscription'
    _description = 'Child Subscription'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'start_date desc'
    
    name = fields.Char('Subscription Number', required=True, copy=False, readonly=True, default='New')
    child_id = fields.Many2one('kids.child', string='Child', required=True, ondelete='cascade')
    package_id = fields.Many2one('subscription.package', string='Package')
    package_ids = fields.Many2many(
        'subscription.package', 
        'child_subscription_package_rel', 
        'subscription_id', 
        'package_id',
        string='Selected Packages'
    )
    start_date = fields.Date('Start Date', required=True, default=fields.Date.today)
    end_date = fields.Date('End Date', compute='_compute_end_date', store=True, readonly=True)
    remaining_days = fields.Integer('Remaining Days', compute='_compute_remaining_days', store=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('paid', 'Paid'),
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', tracking=True)
    activation_date = fields.Datetime('Activation Date', help='Date when subscription was activated (payment received)')
    # Activity status - separate from workflow state
    is_active = fields.Boolean('Is Active', compute='_compute_is_active', store=True)
    activity_status = fields.Char('Activity Status', compute='_compute_activity_status')
    
    # Payment monitoring
    is_fully_paid = fields.Boolean(
        string='Is Fully Paid',
        compute='_compute_payment_status',
        store=True,
        help='True if all invoices are fully paid'
    )
    
    # Visit Tracking Fields
    total_visits_allowed = fields.Integer('Total Visits Allowed', compute='_compute_visit_fields', store=True)
    visits_used = fields.Integer('Visits Used', default=0, tracking=True)
    remaining_visits = fields.Integer('Remaining Visits', compute='_compute_visit_fields', store=True)
    
    # Pricing
    price = fields.Monetary('Price', compute='_compute_price', store=True)
    total_price = fields.Monetary('Total Price', compute='_compute_total_price', store=True)
    currency_id = fields.Many2one('res.currency', string='Currency', 
                                 default=lambda self: self._get_default_currency())
    
    # Payment tracking fields - using Odoo's standard approach
    matched_payment_ids = fields.Many2many(
        string="Matched Payments",
        comodel_name='account.payment',
        relation='kids_child_subscription__account_payment',
        column1='subscription_id',
        column2='payment_id',
        compute='_compute_matched_payment_ids',
        copy=False,
    )
    payment_ids = fields.Many2many('account.payment', compute='_compute_payment_ids', string='Payments')
    payment_count = fields.Integer(compute='_compute_payment_count')
    
    # Payment Integration
    pos_order_id = fields.Many2one('pos.order', string='POS Order', readonly=True)
    invoice_ids = fields.Many2many('account.move', compute='_compute_invoice_ids', string='Invoices')
    invoice_count = fields.Integer('Invoice Count', compute='_compute_invoice_count')
    
    display_name = fields.Char('Display Name', compute='_compute_display_name', store=True)
    
    @api.model
    def create(self, vals):
        """Override create to generate sequence number"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('kids.child.subscription') or 'New'
        return super().create(vals)
    
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
    
    @api.depends('package_id.price', 'package_ids.price')
    def _compute_price(self):
        for record in self:
            if record.package_ids:
                record.price = sum(record.package_ids.mapped('price'))
            else:
                record.price = record.package_id.price if record.package_id else 0.0
    
    @api.depends('package_ids.price')
    def _compute_total_price(self):
        for record in self:
            record.total_price = sum(record.package_ids.mapped('price'))
    
    @api.depends('package_id.number_of_visits', 'package_ids.number_of_visits', 'visits_used')
    def _compute_visit_fields(self):
        """Compute total visits allowed and remaining visits"""
        for record in self:
            # Calculate total visits allowed from packages
            total_visits = 0
            if record.package_ids:
                # For multiple packages, sum all visits
                total_visits = sum(record.package_ids.mapped('number_of_visits'))
            elif record.package_id:
                total_visits = record.package_id.number_of_visits
            
            record.total_visits_allowed = total_visits
            record.remaining_visits = max(0, total_visits - record.visits_used)
    
    @api.depends('start_date', 'package_id.validity_days', 'package_ids.validity_days')
    def _compute_end_date(self):
        """Compute end date based on start date and package validity"""
        for record in self:
            if record.start_date:
                # Get validity days from selected packages or single package
                validity_days = 0
                if record.package_ids:
                    # For multiple packages, use the maximum validity period
                    validity_days = max(record.package_ids.mapped('validity_days')) if record.package_ids else 0
                elif record.package_id:
                    validity_days = record.package_id.validity_days
                
                if validity_days > 0:
                    # Calculate end date by adding validity days to start date
                    from datetime import timedelta
                    record.end_date = record.start_date + timedelta(days=validity_days - 1)
                else:
                    record.end_date = record.start_date
            else:
                record.end_date = False
    
    @api.depends('end_date')
    def _compute_remaining_days(self):
        """Compute remaining days until subscription expires"""
        today = fields.Date.today()
        for record in self:
            if record.end_date:
                if record.end_date >= today:
                    delta = record.end_date - today
                    record.remaining_days = delta.days + 1  # +1 to include today
                else:
                    record.remaining_days = 0  # Expired
            else:
                record.remaining_days = 0
    
    @api.depends('pos_order_id')
    def _compute_invoice_ids(self):
        """Compute related invoices from POS order"""
        for record in self:
            if record.pos_order_id and record.pos_order_id.account_move:
                record.invoice_ids = record.pos_order_id.account_move
            else:
                record.invoice_ids = self.env['account.move']
    
    @api.depends('invoice_ids')
    def _compute_invoice_count(self):
        for record in self:
            record.invoice_count = len(record.invoice_ids)
    
    def _compute_matched_payment_ids(self):
        """Compute matched payments from invoices using Odoo's reconciliation approach"""
        for record in self:
            payments = self.env['account.payment']
            
            if record.invoice_ids:
                for invoice in record.invoice_ids:
                    # Use the invoice's matched_payment_ids if available
                    if hasattr(invoice, 'matched_payment_ids'):
                        payments |= invoice.matched_payment_ids
                    else:
                        # Fallback to reconciliation-based detection
                        receivable_lines = invoice.line_ids.filtered(
                            lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
                        )
                        
                        for line in receivable_lines:
                            reconciled_lines = line.matched_debit_ids.mapped('debit_move_id') | \
                                             line.matched_credit_ids.mapped('credit_move_id')
                            
                            payment_lines = reconciled_lines.filtered(lambda l: l.payment_id)
                            payments |= payment_lines.mapped('payment_id')
            
            record.matched_payment_ids = payments

    def _compute_payment_ids(self):
        """Compute related payments from invoices using reconciliation"""
        for record in self:
            payments = self.env['account.payment']
            
            if record.invoice_ids:
                for invoice in record.invoice_ids:
                    # Get receivable/payable lines from the invoice
                    receivable_lines = invoice.line_ids.filtered(
                        lambda line: line.account_id.account_type in ('asset_receivable', 'liability_payable')
                    )
                    
                    # Get all payments that are reconciled with these lines
                    for line in receivable_lines:
                        # Get reconciled move lines
                        reconciled_lines = line.matched_debit_ids.mapped('debit_move_id') | \
                                         line.matched_credit_ids.mapped('credit_move_id')
                        
                        # Filter for payment move lines and get their payments
                        payment_lines = reconciled_lines.filtered(lambda l: l.payment_id)
                        payments |= payment_lines.mapped('payment_id')
            
            record.payment_ids = payments
    
    @api.depends('matched_payment_ids')
    def _compute_payment_count(self):
        for record in self:
            record.payment_count = len(record.matched_payment_ids)
    
    @api.depends('start_date', 'end_date', 'state')
    def _compute_is_active(self):
        """Compute if subscription is currently active based on dates and payment status"""
        today = fields.Date.today()
        for record in self:
            if record.state == 'paid' and record.start_date and record.end_date:
                record.is_active = record.start_date <= today <= record.end_date
            else:
                record.is_active = False
    
    @api.depends('is_active')
    def _compute_activity_status(self):
        """Compute activity status display"""
        for record in self:
            if record.is_active:
                record.activity_status = 'Active'
            else:
                record.activity_status = 'Inactive'
    
    @api.depends('name', 'child_id.name', 'package_ids', 'start_date')
    def _compute_display_name(self):
        for record in self:
            child_name = record.child_id.name if record.child_id else 'Unknown Child'
            subscription_name = record.name if record.name != 'New' else 'Draft'
            if record.package_ids:
                package_count = len(record.package_ids)
                package_info = f"{package_count} Packages"
            else:
                package_info = record.package_id.name if record.package_id else 'No Package'
            record.display_name = f"{subscription_name} - {child_name} ({package_info})"
    
    def action_confirm(self):
        """Confirm the subscription and redirect to POS for payment"""
        self.ensure_one()
        if not self.package_ids and not self.package_id:
            raise ValidationError("Please select at least one package.")
        
        # Get configured POS for subscriptions
        subscription_pos_id = self.env['ir.config_parameter'].sudo().get_param('kids_club.subscription_pos_id')
        if not subscription_pos_id:
            raise ValidationError("No POS configured for subscriptions. Please configure in Kids Club > Configuration > POS Settings.")
        
        # Validate POS exists and is active
        pos_config = self.env['pos.config'].browse(int(subscription_pos_id))
        if not pos_config.exists():
            raise ValidationError("Configured subscription POS no longer exists. Please update POS Settings.")
        
        # Update subscription state
        self.state = 'confirmed'
        
        # Get customer and product information for POS
        customer = self.child_id.parent_id
        if not customer:
            raise ValidationError(_("Child must have a parent assigned."))
        
        # Get packages to process
        packages = self.package_ids if self.package_ids else [self.package_id] if self.package_id else []
        if not packages:
            raise ValidationError("No packages selected for subscription.")
        
        # Create POS order properly to avoid duplicates
        pos_order = self._create_pos_order_for_subscription(pos_config, customer, packages)
        
        # Show success message and open POS interface
        message = (
            f"Subscription confirmed and POS order created!\n\n"
            f"Customer: {customer.name}\n"
            f"Child: {self.child_id.name}\n"
            f"Packages: {', '.join([pkg.name for pkg in packages if pkg.linked_product_id])}\n"
            f"POS Order: {pos_order.pos_reference}\n\n"
            f"Opening POS interface for payment..."
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Subscription Confirmed - Opening POS',
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': pos_config.open_ui()
            }
        }
    
    def action_cancel(self):
        """Cancel the subscription"""
        for record in self:
            record.state = 'cancelled'
        return True
    
    @api.depends('pos_order_id', 'pos_order_id.state')
    def _compute_payment_status(self):
        """Compute payment status based on POS order and auto-update subscription state"""
        import logging
        _logger = logging.getLogger(__name__)
        
        for record in self:
            _logger.info(f"Checking POS payment status for subscription {record.name}")
            
            if not record.pos_order_id:
                _logger.info(f"No POS order found for subscription {record.name}")
                record.is_fully_paid = False
                continue
            
            _logger.info(f"POS order {record.pos_order_id.name}: state={record.pos_order_id.state}")
            
            # Check if POS order is paid or invoiced (both indicate payment received)
            # POS states: draft, cancel, paid, done
            # Also check invoice_status and account_move for comprehensive coverage
            pos_state = record.pos_order_id.state
            has_invoice = bool(record.pos_order_id.account_move)
            invoice_status = getattr(record.pos_order_id, 'invoice_status', None)
            
            # Payment is received if: state is 'paid' or 'done', OR has invoice (means payment was processed)
            pos_paid = pos_state in ['paid', 'done'] or has_invoice
            record.is_fully_paid = pos_paid
            
            _logger.info(f"POS order state: {pos_state}, invoice_status: {invoice_status}, has_invoice: {has_invoice}, Payment received: {pos_paid}, Current subscription state: {record.state}")
            
            # Auto-update subscription state to 'paid' when POS order is paid or invoiced
            if pos_paid and record.state == 'confirmed':
                _logger.info(f"Updating subscription {record.name} state to 'paid' (POS payment received - state: {record.pos_order_id.state})")
                record.with_context(skip_payment_check=True).write({
                    'state': 'paid',
                    'activation_date': fields.Datetime.now()
                })
            else:
                _logger.info(f"Not updating state: pos_paid={pos_paid}, state={record.state}")
    
    def write(self, vals):
        """Override write to trigger payment status check when invoices change"""
        result = super().write(vals)
        
        # If pos_order_id changed, recompute payment status
        if 'pos_order_id' in vals:
            self._compute_payment_status()
        
        return result
    
    @api.model
    def _check_payment_status_cron(self):
        """Cron job to periodically check and update payment status based on POS orders"""
        # Find all confirmed subscriptions that might need status updates
        confirmed_subscriptions = self.search([
            ('state', '=', 'confirmed'),
            ('pos_order_id', '!=', False)
        ])
        
        for subscription in confirmed_subscriptions:
            subscription._compute_payment_status()
    
    def action_check_payment_status(self):
        """Manual action to check and update payment status"""
        import logging
        _logger = logging.getLogger(__name__)
        
        self.ensure_one()
        _logger.info(f"Manual payment status check triggered for {self.name}")
        
        # Direct payment status check without computed field
        if not self.invoice_ids:
            message = "No invoices found for this subscription."
            _logger.info(message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Payment Status Check',
                    'message': message,
                    'type': 'warning'
                }
            }
        
        posted_invoices = self.invoice_ids.filtered(lambda inv: inv.state == 'posted')
        if not posted_invoices:
            message = f"Found {len(self.invoice_ids)} invoices, but none are posted yet."
            _logger.info(message)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Payment Status Check',
                    'message': message,
                    'type': 'info'
                }
            }
        
        # Check each invoice payment status
        payment_info = []
        all_paid = True
        for invoice in posted_invoices:
            is_paid = invoice.payment_state == 'paid'
            payment_info.append(f"Invoice {invoice.name}: {invoice.payment_state}")
            if not is_paid:
                all_paid = False
        
        _logger.info(f"Payment status check: {payment_info}")
        
        if all_paid and self.state == 'confirmed':
            # Update state directly
            self.write({'state': 'paid'})
            message = f"All invoices are paid! Subscription updated to 'Paid' status.\n\n" + "\n".join(payment_info)
            _logger.info(f"Updated subscription {self.name} to paid status")
        else:
            reason = "not all invoices are paid" if not all_paid else f"subscription state is '{self.state}' (not 'confirmed')"
            message = f"Cannot update to 'Paid' status because {reason}.\n\n" + "\n".join(payment_info)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Payment Status Check Result',
                'message': message,
                'type': 'success' if all_paid else 'warning',
                'sticky': True
            }
        }
    
    def _create_pos_order_for_subscription(self, pos_config, customer, packages):
        """Create POS order for subscription with proper session management"""
        self.ensure_one()
        
        # Check if POS order already exists for this subscription to avoid duplicates
        if self.pos_order_id:
            return self.pos_order_id
            
        # Ensure POS session exists
        if not pos_config.current_session_id:
            session = self.env['pos.session'].create({
                'user_id': self.env.uid,
                'config_id': pos_config.id
            })
        else:
            session = pos_config.current_session_id
        
        # Create POS order with all required fields properly computed
        pos_order_vals = {
            'config_id': pos_config.id,
            'session_id': session.id,
            'partner_id': customer.id,
            'pos_reference': f'SUB-{self.name}',
            'state': 'draft',
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        }
        
        pos_order = self.env['pos.order'].create(pos_order_vals)
        
        # Add order lines for each package
        total_amount = 0.0
        total_tax = 0.0
        
        for package in packages:
            if package.linked_product_id:
                product = package.linked_product_id
                
                # Calculate taxes properly
                taxes = product.taxes_id.filtered(lambda t: t.company_id == pos_config.company_id)
                price_unit = package.price
                
                # Compute tax amount
                tax_results = taxes.compute_all(
                    price_unit, 
                    currency=pos_config.currency_id,
                    quantity=1,
                    product=product,
                    partner=customer
                )
                
                line_tax = tax_results['total_included'] - tax_results['total_excluded']
                
                # Create POS order line with proper tax computation
                self.env['pos.order.line'].create({
                    'order_id': pos_order.id,
                    'product_id': product.id,
                    'qty': 1,
                    'price_unit': price_unit,
                    'price_subtotal': tax_results['total_excluded'],
                    'price_subtotal_incl': tax_results['total_included'],
                    'full_product_name': f"{package.name} - {self.child_id.name}",
                    'tax_ids': [(6, 0, taxes.ids)],
                })
                
                total_amount += tax_results['total_included']
                total_tax += line_tax
        
        # Update POS order with computed totals
        pos_order.write({
            'amount_tax': total_tax,
            'amount_total': total_amount,
        })
        
        # Link POS order to subscription for tracking
        self.pos_order_id = pos_order.id
        
        return pos_order
    
    @api.model
    def create_pos_order_for_subscription(self, subscription_id, pos_config_id):
        """Create POS order for subscription when payment is processed (called from POS)"""
        subscription = self.browse(subscription_id)
        pos_config = self.env['pos.config'].browse(pos_config_id)
        
        if not subscription.exists() or not pos_config.exists():
            return False
            
        # Get customer and packages
        customer = subscription.child_id.parent_id
        packages = subscription.package_ids if subscription.package_ids else [subscription.package_id] if subscription.package_id else []
        
        if not customer or not packages:
            return False
            
        # Use the instance method to create the order
        pos_order = subscription._create_pos_order_for_subscription(pos_config, customer, packages)
        
        return pos_order.id if pos_order else False
    
    def action_view_pos_order(self):
        """Action to view the related POS order"""
        self.ensure_one()
        if not self.pos_order_id:
            raise ValidationError("No POS order found for this subscription.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Order',
            'res_model': 'pos.order',
            'res_id': self.pos_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_invoices(self):
        """Action to view related invoices"""
        self.ensure_one()
        if not self.invoice_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        if len(self.invoice_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoice',
                'res_model': 'account.move',
                'res_id': self.invoice_ids[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': 'Invoices',
                'res_model': 'account.move',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.invoice_ids.ids)],
                'target': 'current',
            }
    
    def action_view_payments(self):
        """Open payment records related to this subscription"""
        if not self.matched_payment_ids:
            return {'type': 'ir.actions.act_window_close'}
        
        if len(self.matched_payment_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Payment'),
                'res_model': 'account.payment',
                'res_id': self.matched_payment_ids[0].id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Payments'),
                'res_model': 'account.payment',
                'view_mode': 'list,form',
                'domain': [('id', 'in', self.matched_payment_ids.ids)],
                'target': 'current',
            }
    
    def _activate_paid_subscriptions(self):
        """Activate subscriptions that are paid and within date range"""
        today = fields.Date.today()
        paid_subscriptions = self.search([
            ('state', '=', 'paid'),
            ('start_date', '<=', today)
        ])
        paid_subscriptions.write({'state': 'active'})
    
    @api.model
    def _cron_update_subscription_status(self):
        """Cron job to update subscription status based on dates and payments"""
        today = fields.Date.today()
        
        # Update payment status for all confirmed subscriptions
        confirmed_subscriptions = self.search([('state', 'in', ['confirmed', 'paid'])])

        
        # Activate paid subscriptions that should be active
        self._activate_paid_subscriptions()
        
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
