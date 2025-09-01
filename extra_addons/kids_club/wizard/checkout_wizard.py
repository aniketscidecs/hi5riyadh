from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CheckoutWizard(models.TransientModel):
    _name = 'kids.checkout.wizard'
    _description = 'Simple Checkout Wizard'
    
    child_id = fields.Many2one('kids.child', string='Child', required=True, readonly=True)
    checkin_id = fields.Many2one('kids.child.checkin', string='Check-in Record', readonly=True)
    
    # Checkout OTP fields
    checkout_otp_sent = fields.Boolean('Checkout OTP Sent', default=False)
    checkout_otp_code = fields.Char('Enter Checkout OTP', size=6)
    sent_checkout_otp_code = fields.Char('Sent Checkout OTP Code', readonly=True, help='OTP code that was sent (for testing)')
    
    # State management
    current_state = fields.Selection([
        ('ready', 'Ready for Checkout'),
        ('pending_otp', 'Pending Checkout OTP'),
        ('completed', 'Checkout Complete')
    ], string='State', default='ready', readonly=True)
    
    @api.model
    def default_get(self, fields_list):
        """Set default values when wizard is opened"""
        res = super().default_get(fields_list)
        
        # Get child_id from context
        child_id = self.env.context.get('default_child_id')
        if child_id:
            # Find active check-in record
            active_checkin = self.env['kids.child.checkin'].search([
                ('child_id', '=', child_id),
                ('state', 'in', ['checked_in', 'pending_checkout_otp'])
            ], limit=1)
            
            if active_checkin:
                res['checkin_id'] = active_checkin.id
                
                # If already in checkout OTP pending state, show that
                if active_checkin.state == 'pending_checkout_otp':
                    res['current_state'] = 'pending_otp'
                    res['checkout_otp_sent'] = True
                    res['sent_checkout_otp_code'] = active_checkin.checkout_otp_code
                else:
                    res['current_state'] = 'ready'
        
        return res
    
    def action_send_checkout_otp(self):
        """Send checkout OTP and update wizard state"""
        self.ensure_one()
        
        if not self.checkin_id:
            raise ValidationError("No active check-in found.")
        
        if self.checkin_id.state != 'checked_in':
            raise ValidationError("Child must be in checked-in state to initiate checkout.")
        
        # Send checkout OTP
        result = self.checkin_id.action_checkout()
        
        # Update wizard state
        self.current_state = 'pending_otp'
        self.checkout_otp_sent = True
        self.sent_checkout_otp_code = self.checkin_id.checkout_otp_code
        
        # Return action to refresh wizard and show OTP input
        return {
            'type': 'ir.actions.act_window',
            'name': 'Checkout - Enter OTP',
            'res_model': 'kids.checkout.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_verify_checkout_otp(self):
        """Verify checkout OTP and complete checkout"""
        self.ensure_one()
        
        if not self.checkout_otp_code:
            raise ValidationError("Please enter the checkout OTP provided by the parent.")
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found.")
        
        # Verify checkout OTP
        try:
            result = self.checkin_id.action_verify_checkout_otp(self.checkout_otp_code)
            
            # Update wizard state
            self.current_state = 'completed'
            
            # Return success message and close wizard
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Checkout Complete!',
                    'message': f'{self.child_id.name} has been successfully checked out.',
                    'type': 'success'
                }
            }
            
        except ValidationError as e:
            raise ValidationError(str(e))
    
    def action_resend_checkout_otp(self):
        """Resend checkout OTP"""
        self.ensure_one()
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found.")
        
        # Resend checkout OTP
        result = self.checkin_id.action_resend_checkout_otp()
        self.checkout_otp_code = False  # Clear previous OTP entry
        self.sent_checkout_otp_code = self.checkin_id.checkout_otp_code
        
        # Return action to refresh wizard
        return {
            'type': 'ir.actions.act_window',
            'name': 'Checkout - Enter OTP',
            'res_model': 'kids.checkout.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
