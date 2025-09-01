from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta
import random
import string


class ChildCheckin(models.Model):
    _name = 'kids.child.checkin'
    _description = 'Child Check-in/Check-out'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'checkin_time desc'
    
    name = fields.Char('Check-in Number', required=True, copy=False, readonly=True, default='New')
    child_id = fields.Many2one('kids.child', string='Child', required=True, ondelete='cascade')
    room_id = fields.Many2one('kids.room', string='Room', 
                             help="Room where the child will be playing")
    subscription_id = fields.Many2one('kids.child.subscription', string='Subscription', required=True)
    
    # Check-in/Check-out times
    checkin_time = fields.Datetime('Check-in Time', default=fields.Datetime.now, required=True)
    checkout_time = fields.Datetime('Check-out Time')
    duration_minutes = fields.Integer('Duration (Minutes)', compute='_compute_duration', store=True)
    
    # OTP for check-in verification
    otp_code = fields.Char('OTP Code', size=6)
    otp_verified = fields.Boolean('OTP Verified', default=False)
    otp_sent_time = fields.Datetime('OTP Sent Time')
    otp_verified_time = fields.Datetime('OTP Verified Time')
    entered_otp = fields.Char('Enter OTP', help='Enter the OTP provided by parent')
    
    # OTP for check-out verification
    checkout_otp_code = fields.Char('Checkout OTP Code', size=6)
    checkout_otp_verified = fields.Boolean('Checkout OTP Verified', default=False)
    checkout_otp_sent_time = fields.Datetime('Checkout OTP Sent Time')
    checkout_otp_verified_time = fields.Datetime('Checkout OTP Verified Time')
    entered_checkout_otp = fields.Char('Enter Checkout OTP', help='Enter the OTP provided by parent for checkout')
    
    # Time calculations
    free_minutes_used = fields.Integer('Free Minutes Used', compute='_compute_time_usage', store=True)
    extra_minutes = fields.Integer('Extra Minutes', compute='_compute_time_usage', store=True)
    extra_charges = fields.Monetary('Extra Charges', compute='_compute_extra_charges', store=True)
    currency_id = fields.Many2one('res.currency', related='subscription_id.currency_id')
    
    # Live timer display with seconds
    live_timer = fields.Char('Live Timer', compute='_compute_live_timer')
    
    # Payment confirmation
    payment_confirmed = fields.Boolean('Payment Confirmed', default=False)
    payment_confirmation_time = fields.Datetime('Payment Confirmed Time')
    
    # Status
    state = fields.Selection([
        ('pending_otp', 'Pending Check-in OTP'),
        ('checked_in', 'Checked In'),
        ('pending_payment', 'Pending Payment Confirmation'),
        ('pending_checkout_otp', 'Pending Check-out OTP'),
        ('checked_out', 'Checked Out'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='pending_otp', tracking=True)
    
    # Extra billing
    extra_invoice_id = fields.Many2one('account.move', string='Extra Time Invoice')
    
    @api.model
    def create(self, vals):
        """Override create to generate sequence number and validate room capacity"""
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('kids.child.checkin') or 'New'
        
        # Validate room capacity before creating check-in (only if room is specified)
        if vals.get('room_id'):
            self._validate_room_capacity(vals['room_id'])
        
        return super().create(vals)
    
    def write(self, vals):
        """Override write to validate room capacity when room is changed"""
        if vals.get('room_id'):
            for record in self:
                # Only validate if room is being changed and record is being checked in
                if record.room_id.id != vals['room_id'] and record.state in ['pending_otp', 'checked_in']:
                    self._validate_room_capacity(vals['room_id'], exclude_record=record)
        
        return super().write(vals)
    
    def _validate_room_capacity(self, room_id, exclude_record=None):
        """Validate that room has available capacity"""
        room = self.env['kids.room'].browse(room_id)
        if not room.exists():
            raise ValidationError("Selected room does not exist.")
        
        # Count current check-ins in this room (excluding the current record if updating)
        domain = [('room_id', '=', room_id), ('state', '=', 'checked_in')]
        if exclude_record:
            domain.append(('id', '!=', exclude_record.id))
        
        current_checkins = self.search_count(domain)
        
        if current_checkins >= room.capacity:
            raise ValidationError(
                f"Room '{room.name}' is at full capacity ({room.capacity} children). "
                f"Please select a different room or wait for a child to check out."
            )
    
    @api.depends('checkin_time', 'checkout_time')
    def _compute_duration(self):
        """Compute duration in minutes"""
        for record in self:
            if record.checkin_time and record.checkout_time:
                delta = record.checkout_time - record.checkin_time
                record.duration_minutes = int(delta.total_seconds() / 60)
            elif record.checkin_time and not record.checkout_time:
                # For ongoing sessions, calculate current duration
                delta = fields.Datetime.now() - record.checkin_time
                record.duration_minutes = int(delta.total_seconds() / 60)
            else:
                record.duration_minutes = 0
    
    @api.depends('checkin_time', 'checkout_time', 'state')
    def _compute_live_timer(self):
        """Compute live timer display with hours, minutes, and seconds"""
        for record in self:
            if record.state == 'checked_in' and record.checkin_time and not record.checkout_time:
                # Calculate current duration for active check-ins
                delta = fields.Datetime.now() - record.checkin_time
                total_seconds = int(delta.total_seconds())
                
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                
                if hours > 0:
                    record.live_timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    record.live_timer = f"{minutes:02d}:{seconds:02d}"
            elif record.checkout_time:
                # For completed check-ins, show final duration
                delta = record.checkout_time - record.checkin_time
                total_seconds = int(delta.total_seconds())
                
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                seconds = total_seconds % 60
                
                if hours > 0:
                    record.live_timer = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    record.live_timer = f"{minutes:02d}:{seconds:02d}"
            else:
                record.live_timer = "00:00"
    
    @api.depends('duration_minutes', 'subscription_id')
    def _compute_time_usage(self):
        """Compute free minutes used and extra minutes"""
        for record in self:
            if not record.subscription_id or record.duration_minutes <= 0:
                record.free_minutes_used = 0
                record.extra_minutes = 0
                continue
            
            # Get daily free minutes from packages
            daily_free_minutes = 0
            margin_minutes = 0
            
            if record.subscription_id.package_ids:
                # For multiple packages, use maximum daily free minutes
                daily_free_minutes = max(record.subscription_id.package_ids.mapped('daily_free_minutes') or [0])
                margin_minutes = max(record.subscription_id.package_ids.mapped('margin_minutes') or [0])
            elif record.subscription_id.package_id:
                daily_free_minutes = record.subscription_id.package_id.daily_free_minutes
                margin_minutes = record.subscription_id.package_id.margin_minutes
            
            total_free_time = daily_free_minutes + margin_minutes
            
            if record.duration_minutes <= total_free_time:
                record.free_minutes_used = record.duration_minutes
                record.extra_minutes = 0
            else:
                record.free_minutes_used = total_free_time
                record.extra_minutes = record.duration_minutes - total_free_time
    
    @api.depends('extra_minutes', 'subscription_id')
    def _compute_extra_charges(self):
        """Compute extra charges for overtime using per-minute pricing"""
        for record in self:
            if record.extra_minutes <= 0 or not record.subscription_id:
                record.extra_charges = 0.0
                continue
            
            # Get per-minute charge rate from packages
            per_minute_rate = 0.0
            
            if record.subscription_id.package_ids:
                # For multiple packages, use maximum per-minute rate
                rates = record.subscription_id.package_ids.mapped('extra_time_charge_per_minute')
                per_minute_rate = max(rates) if rates else 0.0
            elif record.subscription_id.package_id:
                per_minute_rate = record.subscription_id.package_id.extra_time_charge_per_minute
            
            if per_minute_rate > 0:
                # Calculate charges: extra_minutes * per_minute_rate
                record.extra_charges = record.extra_minutes * per_minute_rate
            else:
                record.extra_charges = 0.0
    
    def action_send_otp(self):
        """Send OTP to parent for check-in verification"""
        self.ensure_one()
        
        # Generate 6-digit OTP
        otp = ''.join(random.choices(string.digits, k=6))
        self.write({
            'otp_code': otp,
            'otp_sent_time': fields.Datetime.now()
        })
        
        # Send OTP via email/SMS
        self._send_otp_notification(otp)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'OTP Sent',
                'message': f'OTP has been sent to parent of {self.child_id.name}',
                'type': 'success'
            }
        }
    
    def action_resend_otp(self):
        """Resend OTP to parent - generates new OTP"""
        self.ensure_one()
        
        # Clear previous entered OTP
        self.entered_otp = False
        
        # Generate new OTP and send
        self.action_send_otp()
        
        # Return action to refresh the form view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Check-in Record',
            'res_model': 'kids.child.checkin',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
            }
        }
    
    def verify_otp_action(self):
        """Action method called by the Verify OTP button"""
        self.ensure_one()
        
        if not self.entered_otp:
            raise ValidationError("Please enter the OTP provided by the parent.")
        
        # Call the existing verification method
        result = self.action_verify_otp(self.entered_otp)
        
        # Return action to refresh the form and show updated state
        return {
            'type': 'ir.actions.act_window',
            'name': 'Check-in Record',
            'res_model': 'kids.child.checkin',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'readonly',
            }
        }
    
    def action_verify_otp(self, entered_otp):
        """Verify OTP and complete check-in"""
        self.ensure_one()
        
        if not self.otp_code:
            raise ValidationError("No OTP has been sent. Please send OTP first.")
        
        if entered_otp != self.otp_code:
            raise ValidationError("Invalid OTP. Please try again.")
        
        # Check OTP expiry (5 minutes)
        if self.otp_sent_time:
            expiry_time = self.otp_sent_time + timedelta(minutes=5)
            if fields.Datetime.now() > expiry_time:
                raise ValidationError("OTP has expired. Please request a new OTP.")
        
        # Verify OTP and complete check-in
        self.write({
            'otp_verified': True,
            'otp_verified_time': fields.Datetime.now(),
            'state': 'checked_in',
            'checkin_time': fields.Datetime.now()  # Set actual check-in time
        })
        
        # Update subscription visit count
        if self.subscription_id:
            self.subscription_id.visits_used += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Check-in Successful',
                'message': f'{self.child_id.name} has been checked in successfully!',
                'type': 'success'
            }
        }
    
    def action_checkout(self):
        """Open checkout wizard from dashboard"""
        self.ensure_one()
        if self.state != 'checked_in':
            raise ValidationError("Child is not currently checked in.")
        
        # Open the checkin wizard in checkout mode
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quick Check-in/Check-out',
            'res_model': 'kids.checkin.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_child_id': self.child_id.id,
                'default_checkin_id': self.id,
                'default_action_type': 'checkout',
            }
        }
    
    def action_dashboard_checkout(self):
        """Use the same working checkout wizard as child form smart button"""
        self.ensure_one()
        if self.state != 'checked_in':
            raise ValidationError("Child is not currently checked in.")
        
        # Use the exact same working checkout wizard as child form smart button
        return {
            'type': 'ir.actions.act_window',
            'name': 'Checkout',
            'res_model': 'kids.checkout.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_child_id': self.child_id.id,
            },
        }
    
    def action_confirm_payment(self):
        """Confirm payment for extra charges and proceed to OTP verification"""
        self.ensure_one()
        if self.state != 'pending_payment':
            raise ValidationError("Payment confirmation is not required at this stage.")
        
        # Confirm payment
        self.write({
            'payment_confirmed': True,
            'payment_confirmation_time': fields.Datetime.now(),
        })
        
        # Proceed to checkout OTP
        self.action_send_checkout_otp()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Payment Confirmed',
                'message': f'Payment of {self.extra_charges:.2f} {self.currency_id.symbol} confirmed. Checkout OTP has been sent.',
                'type': 'success'
            }
        }
    
    def action_send_checkout_otp(self):
        """Send OTP to parent for check-out verification"""
        self.ensure_one()
        
        # Generate 6-digit OTP for checkout
        otp = ''.join(random.choices(string.digits, k=6))
        self.write({
            'checkout_otp_code': otp,
            'checkout_otp_sent_time': fields.Datetime.now()
        })
        
        # Send OTP via email/SMS
        self._send_checkout_otp_notification(otp)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Checkout OTP Sent',
                'message': f'Checkout OTP has been sent to parent of {self.child_id.name}',
                'type': 'success'
            }
        }
    
    def action_resend_checkout_otp(self):
        """Resend checkout OTP to parent - generates new OTP"""
        self.ensure_one()
        
        # Clear previous entered checkout OTP
        self.entered_checkout_otp = False
        
        # Generate new checkout OTP and send
        self.action_send_checkout_otp()
        
        # Return action to refresh the form view
        return {
            'type': 'ir.actions.act_window',
            'name': 'Check-in Record',
            'res_model': 'kids.child.checkin',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'edit',
            }
        }
    
    def verify_checkout_otp_action(self):
        """Action method called by the Verify Checkout OTP button"""
        self.ensure_one()
        
        if not self.entered_checkout_otp:
            raise ValidationError("Please enter the checkout OTP provided by the parent.")
        
        # Call the verification method
        result = self.action_verify_checkout_otp(self.entered_checkout_otp)
        
        # Return action to refresh the form and show updated state
        return {
            'type': 'ir.actions.act_window',
            'name': 'Check-in Record',
            'res_model': 'kids.child.checkin',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'form_view_initial_mode': 'readonly',
            }
        }
    
    def action_verify_checkout_otp(self, entered_otp):
        """Verify checkout OTP and complete check-out"""
        self.ensure_one()
        
        if not self.checkout_otp_code:
            raise ValidationError("No checkout OTP has been sent. Please send checkout OTP first.")
        
        if entered_otp != self.checkout_otp_code:
            raise ValidationError("Invalid checkout OTP. Please try again.")
        
        # Check OTP expiry (5 minutes)
        if self.checkout_otp_sent_time:
            expiry_time = self.checkout_otp_sent_time + timedelta(minutes=5)
            if fields.Datetime.now() > expiry_time:
                raise ValidationError("Checkout OTP has expired. Please request a new OTP.")
        
        # Verify OTP and complete check-out
        self.write({
            'checkout_otp_verified': True,
            'checkout_otp_verified_time': fields.Datetime.now(),
            'checkout_time': fields.Datetime.now(),
            'state': 'checked_out'
        })
        
        # Create invoice for extra charges if any
        if self.extra_charges > 0:
            self._create_extra_charges_invoice()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Check-out Successful',
                'message': f'{self.child_id.name} has been checked out successfully!',
                'type': 'success'
            }
        }
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Check-out Successful',
                'message': f'{self.child_id.name} has been checked out. Duration: {self.duration_minutes} minutes.',
                'type': 'success'
            }
        }
    
    def _send_otp_notification(self, otp):
        """Send OTP notification to parent via email/SMS"""
        # Email notification
        if self.child_id.parent_id.email:
            # Create email body
            body = f"""
            Dear {self.child_id.parent_id.name},
            
            Your child {self.child_id.name} is requesting to check-in to Hi5 Kids Club.
            
            Your OTP for check-in verification is: {otp}
            
            This OTP is valid for 5 minutes only.
            
            Best regards,
            Hi5 Kids Club Team
            """
            
            # Send email
            mail_values = {
                'subject': f'Check-in OTP for {self.child_id.name}',
                'body_html': body.replace('\n', '<br>'),
                'email_to': self.child_id.parent_id.email,
                'email_from': self.env.company.email or 'noreply@hi5kidsclub.com',
            }
            
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
        
        # SMS notification (placeholder - implement based on your SMS provider)
        if self.child_id.parent_id.mobile:
            # Add SMS implementation here
            pass
    
    def _send_checkout_otp_notification(self, otp):
        """Send checkout OTP notification to parent via email/SMS"""
        # Email notification
        if self.child_id.parent_id.email:
            # Create email body
            body = f"""
            Dear {self.child_id.parent_id.name},
            
            Your child {self.child_id.name} is ready to check-out from Hi5 Kids Club.
            
            Your OTP for check-out verification is: {otp}
            
            This OTP is valid for 5 minutes only.
            
            Best regards,
            Hi5 Kids Club Team
            """
            
            # Send email
            mail_values = {
                'subject': f'Check-out OTP for {self.child_id.name}',
                'body_html': body.replace('\n', '<br>'),
                'email_to': self.child_id.parent_id.email,
                'email_from': self.env.company.email or 'noreply@hi5kidsclub.com',
            }
            
            mail = self.env['mail.mail'].create(mail_values)
            mail.send()
        
        # SMS notification (placeholder - implement based on your SMS provider)
        if self.child_id.parent_id.mobile:
            # Add SMS implementation here
            pass
    
    def _create_extra_charges_invoice(self):
        """Create invoice for extra time charges"""
        if self.extra_charges <= 0:
            return
        
        # Find income account (Odoo 17+ uses account_type instead of user_type_id)
        income_account = self.env['account.account'].search([
            ('account_type', 'in', ['income', 'income_other'])
        ], limit=1)
        
        if not income_account:
            # Fallback to any receivable account
            income_account = self.env['account.account'].search([
                ('account_type', '=', 'asset_receivable')
            ], limit=1)
        
        # Create invoice
        invoice_vals = {
            'move_type': 'out_invoice',
            'partner_id': self.child_id.parent_id.id,
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': [(0, 0, {
                'name': f'Extra Time Charges - {self.child_id.name} ({self.extra_minutes} minutes)',
                'quantity': 1,
                'price_unit': self.extra_charges,
                'account_id': income_account.id if income_account else False,
            })]
        }
        
        invoice = self.env['account.move'].create(invoice_vals)
        self.extra_invoice_id = invoice.id
        
        return invoice
    
    def action_view_extra_invoice(self):
        """View the extra charges invoice"""
        self.ensure_one()
        if not self.extra_invoice_id:
            return {'type': 'ir.actions.act_window_close'}
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Extra Time Invoice',
            'res_model': 'account.move',
            'res_id': self.extra_invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def validate_active_subscription(self, child_id):
        """Validate if child has active subscription for check-in"""
        child = self.env['kids.child'].browse(child_id)
        
        if not child.exists():
            return {'valid': False, 'message': 'Child not found'}
        
        # Check if child has active subscription (paid subscriptions that are within date range)
        active_subscription = child.subscription_ids.filtered(
            lambda s: s.state in ['active', 'paid'] and s.is_active and s.remaining_visits > 0
        )
        
        if not active_subscription:
            return {
                'valid': False, 
                'message': 'No active subscription found or no remaining visits'
            }
        
        # Check if child is already checked in
        if child.is_checked_in:
            return {
                'valid': False,
                'message': 'Child is already checked in'
            }
        
        return {
            'valid': True,
            'subscription': active_subscription[0],
            'message': 'Ready for check-in'
        }
    
    @api.model
    def create_checkin_request(self, child_id, room_id=None):
        """Create a new check-in request and send OTP"""
        validation = self.validate_active_subscription(child_id)
        
        if not validation['valid']:
            raise ValidationError(validation['message'])
        
        # Create check-in record
        vals = {
            'child_id': child_id,
            'subscription_id': validation['subscription'].id,
        }
        if room_id:
            vals['room_id'] = room_id
            
        checkin = self.create(vals)
        
        # Send OTP
        checkin.action_send_otp()
        
        return checkin


class CheckinDashboard(models.Model):
    _name = 'kids.checkin.dashboard'
    _description = 'Check-in Dashboard for Real-time Monitoring'
    
    @api.model
    def get_active_checkins(self):
        """Get all currently active check-ins for dashboard"""
        active_checkins = self.env['kids.child.checkin'].search([
            ('state', '=', 'checked_in'),
            ('checkout_time', '=', False)
        ])
        
        result = []
        for checkin in active_checkins:
            result.append({
                'id': checkin.id,
                'child_name': checkin.child_id.name,
                'child_image': checkin.child_id.image_small,
                'barcode_id': checkin.child_id.barcode_id,
                'checkin_time': checkin.checkin_time,
                'duration_minutes': checkin.duration_minutes,
                'free_minutes_used': checkin.free_minutes_used,
                'extra_minutes': checkin.extra_minutes,
                'extra_charges': checkin.extra_charges,
                'subscription_name': checkin.subscription_id.display_name,
                'parent_name': checkin.child_id.parent_id.name,
                'parent_phone': checkin.child_id.parent_id.phone,
            })
        
        return result
    
    @api.model
    def get_dashboard_stats(self):
        """Get dashboard statistics"""
        today = fields.Date.today()
        
        # Today's stats
        today_checkins = self.env['kids.child.checkin'].search([
            ('checkin_time', '>=', today),
            ('checkin_time', '<', today + timedelta(days=1))
        ])
        
        active_now = today_checkins.filtered(lambda c: c.state == 'checked_in')
        completed_today = today_checkins.filtered(lambda c: c.state == 'checked_out')
        
        return {
            'active_checkins': len(active_now),
            'completed_today': len(completed_today),
            'total_today': len(today_checkins),
            'total_revenue_today': sum(completed_today.mapped('extra_charges')),
        }
