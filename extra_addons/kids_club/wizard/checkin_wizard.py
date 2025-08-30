from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CheckinWizard(models.TransientModel):
    _name = 'kids.checkin.wizard'
    _description = 'Quick Check-in Wizard'
    
    child_id = fields.Many2one('kids.child', string='Child', required=True)
    barcode_scan = fields.Char('Scan Barcode', help='Scan or enter child barcode')
    
    # Validation fields
    subscription_id = fields.Many2one('kids.child.subscription', string='Active Subscription', readonly=True)
    remaining_visits = fields.Integer('Remaining Visits', readonly=True)
    validation_message = fields.Text('Validation Message', readonly=True)
    
    # OTP fields
    otp_sent = fields.Boolean('OTP Sent', default=False)
    otp_code = fields.Char('Enter OTP', size=6)
    
    # Internal fields
    checkin_id = fields.Many2one('kids.child.checkin', string='Check-in Record')
    
    @api.onchange('barcode_scan')
    def _onchange_barcode_scan(self):
        """Auto-select child based on barcode scan"""
        if self.barcode_scan:
            child = self.env['kids.child'].search([
                ('barcode_id', '=', self.barcode_scan.strip())
            ], limit=1)
            
            if child:
                self.child_id = child
                self.barcode_scan = False  # Clear the field after successful scan
            else:
                return {
                    'warning': {
                        'title': 'Barcode Not Found',
                        'message': f'No child found with barcode: {self.barcode_scan}'
                    }
                }
    
    @api.onchange('child_id')
    def _onchange_child_id(self):
        """Validate child subscription when child is selected"""
        if self.child_id:
            validation = self.env['kids.child.checkin'].validate_active_subscription(self.child_id.id)
            
            if validation['valid']:
                self.subscription_id = validation['subscription']
                self.remaining_visits = validation['subscription'].remaining_visits
                self.validation_message = False
            else:
                self.subscription_id = False
                self.remaining_visits = 0
                self.validation_message = validation['message']
        else:
            self.subscription_id = False
            self.remaining_visits = 0
            self.validation_message = False
    
    def action_send_otp(self):
        """Send OTP for check-in verification"""
        self.ensure_one()
        
        if not self.child_id:
            raise ValidationError("Please select a child first.")
        
        if self.validation_message:
            raise ValidationError(self.validation_message)
        
        # Create check-in record and send OTP
        checkin = self.env['kids.child.checkin'].create_checkin_request(self.child_id.id)
        
        self.checkin_id = checkin
        self.otp_sent = True
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'OTP Sent',
                'message': f'OTP has been sent to parent of {self.child_id.name}',
                'type': 'success'
            }
        }
    
    def action_verify_checkin(self):
        """Verify OTP and complete check-in"""
        self.ensure_one()
        
        if not self.otp_code:
            raise ValidationError("Please enter the OTP code.")
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found. Please send OTP first.")
        
        # Verify OTP
        try:
            result = self.checkin_id.action_verify_otp(self.otp_code)
            
            # Close wizard and show success
            return {
                'type': 'ir.actions.act_window',
                'name': 'Check-in Successful',
                'res_model': 'kids.child.checkin',
                'res_id': self.checkin_id.id,
                'view_mode': 'form',
                'target': 'current',
            }
            
        except ValidationError as e:
            raise ValidationError(str(e))
    
    def action_quick_checkout(self):
        """Quick checkout for already checked-in children"""
        self.ensure_one()
        
        if not self.child_id:
            raise ValidationError("Please select a child first.")
        
        # Find active check-in
        active_checkin = self.env['kids.child.checkin'].search([
            ('child_id', '=', self.child_id.id),
            ('state', '=', 'checked_in')
        ], limit=1)
        
        if not active_checkin:
            raise ValidationError("Child is not currently checked in.")
        
        # Perform checkout
        result = active_checkin.action_checkout()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Check-out Complete',
            'res_model': 'kids.child.checkin',
            'res_id': active_checkin.id,
            'view_mode': 'form',
            'target': 'current',
        }
