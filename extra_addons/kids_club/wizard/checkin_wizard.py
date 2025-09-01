from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class CheckinWizard(models.TransientModel):
    _name = 'kids.checkin.wizard'
    _description = 'Quick Check-in Wizard'
    
    child_id = fields.Many2one('kids.child', string='Child', required=True)
    room_id = fields.Many2one('kids.room', string='Room', 
                             help="Room where the child will be playing")
    
    @api.model
    def default_get(self, fields_list):
        """Set default values and detect pending OTP states when wizard opens"""
        res = super().default_get(fields_list)
        
        # Get child_id from context
        child_id = self.env.context.get('default_child_id')
        if child_id:
            res['child_id'] = child_id
            
            # Check for existing check-in record and set appropriate state
            existing_checkin = self.env['kids.child.checkin'].search([
                ('child_id', '=', child_id),
                ('state', 'in', ['pending_otp', 'checked_in', 'pending_checkout_otp'])
            ], limit=1)
            
            if existing_checkin:
                res['checkin_id'] = existing_checkin.id
                res['current_state'] = existing_checkin.state
                
                if existing_checkin.state == 'pending_otp':
                    res['otp_sent'] = True
                    res['sent_otp_code'] = existing_checkin.otp_code
                elif existing_checkin.state == 'pending_checkout_otp':
                    res['checkout_otp_sent'] = True
                    res['sent_checkout_otp_code'] = existing_checkin.checkout_otp_code
                
                # Set subscription info if available
                if existing_checkin.subscription_id:
                    res['subscription_id'] = existing_checkin.subscription_id.id
                    res['remaining_visits'] = existing_checkin.subscription_id.remaining_visits
                    
                if existing_checkin.state in ['checked_in', 'pending_checkout_otp']:
                    res['validation_message'] = "Child is already checked in"
            else:
                res['current_state'] = 'new'
                
                # Validate subscription for new check-ins
                validation = self.env['kids.child.checkin'].validate_active_subscription(child_id)
                if validation['valid']:
                    res['subscription_id'] = validation['subscription'].id
                    res['remaining_visits'] = validation['subscription'].remaining_visits
                else:
                    res['validation_message'] = validation['message']
        
        return res
    barcode_scan = fields.Char('Scan Barcode', help='Scan or enter child barcode')
    
    # Validation fields
    subscription_id = fields.Many2one('kids.child.subscription', string='Active Subscription', readonly=True)
    remaining_visits = fields.Integer('Remaining Visits', readonly=True)
    validation_message = fields.Text('Validation Message', readonly=True)
    
    # OTP fields
    otp_sent = fields.Boolean('OTP Sent', default=False)
    otp_code = fields.Char('Enter OTP', size=6)
    sent_otp_code = fields.Char('Sent OTP Code', readonly=True, help='OTP code that was sent (for testing)')
    
    # Checkout OTP fields
    checkout_otp_sent = fields.Boolean('Checkout OTP Sent', default=False)
    checkout_otp_code = fields.Char('Enter Checkout OTP', size=6)
    sent_checkout_otp_code = fields.Char('Sent Checkout OTP Code', readonly=True, help='Checkout OTP code that was sent (for testing)')
    
    # Internal fields
    checkin_id = fields.Many2one('kids.child.checkin', string='Check-in Record')
    current_state = fields.Selection([
        ('new', 'New'),
        ('pending_otp', 'Pending Check-in OTP'),
        ('checked_in', 'Checked In'),
        ('pending_checkout_otp', 'Pending Check-out OTP'),
        ('checked_out', 'Checked Out')
    ], string='Current State', default='new', readonly=True)
    
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
            # Check for existing check-in record
            existing_checkin = self.env['kids.child.checkin'].search([
                ('child_id', '=', self.child_id.id),
                ('state', 'in', ['pending_otp', 'checked_in', 'pending_checkout_otp'])
            ], limit=1)
            
            if existing_checkin:
                self.checkin_id = existing_checkin
                self.current_state = existing_checkin.state
                if existing_checkin.state == 'pending_otp':
                    self.otp_sent = True
                    # Populate sent OTP code for display
                    self.sent_otp_code = existing_checkin.otp_code
                elif existing_checkin.state == 'pending_checkout_otp':
                    self.checkout_otp_sent = True
                    # Populate sent checkout OTP code for display
                    self.sent_checkout_otp_code = existing_checkin.checkout_otp_code
            else:
                self.checkin_id = False
                self.current_state = 'new'
                self.otp_sent = False
                self.checkout_otp_sent = False
            
            validation = self.env['kids.child.checkin'].validate_active_subscription(self.child_id.id)
            
            if validation['valid']:
                self.subscription_id = validation['subscription']
                self.remaining_visits = validation['subscription'].remaining_visits
                # Only show validation message if there's no existing check-in (to avoid confusion)
                if not existing_checkin:
                    self.validation_message = False
            else:
                # Only clear subscription fields if there's no existing check-in
                if not existing_checkin:
                    self.subscription_id = False
                    self.remaining_visits = 0
                    self.validation_message = validation['message']
                else:
                    # For existing check-ins, try to get subscription from the check-in record
                    if existing_checkin.subscription_id:
                        self.subscription_id = existing_checkin.subscription_id
                        self.remaining_visits = existing_checkin.subscription_id.remaining_visits
                    self.validation_message = "Child is already checked in"
        else:
            self.subscription_id = False
            self.remaining_visits = 0
            self.validation_message = False
            self.checkin_id = False
            self.current_state = 'new'
            self.otp_sent = False
            self.checkout_otp_sent = False
    
    def action_send_otp(self):
        """Send OTP for check-in verification"""
        self.ensure_one()
        
        if not self.child_id:
            raise ValidationError("Please select a child first.")
        
        # Check if there's a blocking validation issue (not just informational)
        if self.validation_message and not self.subscription_id:
            raise ValidationError(self.validation_message)
        
        # If child is already checked in, don't allow new check-in
        if self.checkin_id and self.checkin_id.state == 'checked_in':
            raise ValidationError("Child is already checked in. Use checkout option instead.")
        
        # If there's already a pending OTP, just refresh the wizard to show it
        if self.checkin_id and self.checkin_id.state == 'pending_otp':
            # Just refresh the wizard to show existing OTP input
            self.otp_sent = True
            self.current_state = 'pending_otp'
            self.sent_otp_code = self.checkin_id.otp_code
            # Trigger onchange to repopulate subscription fields
            self._onchange_child_id()
            return {
                'type': 'ir.actions.act_window',
                'name': 'Quick Check-in/Check-out',
                'res_model': 'kids.checkin.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': self.env.context,
            }
        
        # Create check-in record and send OTP
        checkin = self.env['kids.child.checkin'].create_checkin_request(self.child_id.id, self.room_id.id if self.room_id else None)
        
        self.checkin_id = checkin
        self.otp_sent = True
        self.current_state = 'pending_otp'
        # Store the sent OTP code for display (testing purposes)
        self.sent_otp_code = checkin.otp_code
        
        # Trigger onchange to repopulate subscription fields after wizard reload
        self._onchange_child_id()
        
        # Return action to reload the wizard with updated state
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quick Check-in/Check-out',
            'res_model': 'kids.checkin.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_verify_checkin(self):
        """Verify OTP and complete check-in"""
        self.ensure_one()
        
        if not self.otp_code:
            raise ValidationError("Please enter the OTP provided by the parent.")
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found. Please send OTP first.")
        
        # Verify OTP
        try:
            result = self.checkin_id.action_verify_otp(self.otp_code)
            
            # Auto-close wizard after successful check-in
            return {
                'type': 'ir.actions.act_window_close'
            }
            
        except ValidationError as e:
            raise ValidationError(str(e))
    
    def action_send_checkout_otp(self):
        """Send checkout OTP for verification"""
        self.ensure_one()
        
        if not self.child_id:
            raise ValidationError("Please select a child first.")
        
        if not self.checkin_id or self.checkin_id.state != 'checked_in':
            raise ValidationError("Child is not currently checked in.")
        
        # Send OTP directly (not through action_checkout)
        self.checkin_id.action_send_checkout_otp()
        
        # Update wizard state
        self.checkout_otp_sent = True
        self.current_state = 'pending_checkout_otp'
        # Store the sent checkout OTP code for display (testing purposes)
        self.sent_checkout_otp_code = self.checkin_id.checkout_otp_code
        
        # Trigger onchange to repopulate subscription fields after wizard reload
        self._onchange_child_id()
        
        # Return action to reload the wizard with updated state
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quick Check-in/Check-out',
            'res_model': 'kids.checkin.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_verify_checkout(self):
        """Verify checkout OTP and complete check-out"""
        self.ensure_one()
        
        if not self.checkout_otp_code:
            raise ValidationError("Please enter the checkout OTP code.")
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found.")
        
        # Verify checkout OTP
        try:
            result = self.checkin_id.action_verify_checkout_otp(self.checkout_otp_code)
            
            # Auto-close wizard after successful checkout
            return {
                'type': 'ir.actions.act_window_close'
            }
            
        except ValidationError as e:
            raise ValidationError(str(e))
    
    def action_resend_checkin_otp(self):
        """Resend check-in OTP"""
        self.ensure_one()
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found.")
        
        # Resend OTP
        result = self.checkin_id.action_resend_otp()
        self.otp_code = False  # Clear previous OTP entry
        
        # Trigger onchange to repopulate subscription fields after wizard reload
        self._onchange_child_id()
        
        # Return action to reload the wizard with updated state
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quick Check-in/Check-out',
            'res_model': 'kids.checkin.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_resend_checkout_otp(self):
        """Resend checkout OTP"""
        self.ensure_one()
        
        if not self.checkin_id:
            raise ValidationError("No check-in record found.")
        
        # Resend checkout OTP
        result = self.checkin_id.action_resend_checkout_otp()
        self.checkout_otp_code = False  # Clear previous OTP entry
        
        # Trigger onchange to repopulate subscription fields after wizard reload
        self._onchange_child_id()
        
        # Return action to reload the wizard with updated state
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quick Check-in/Check-out',
            'res_model': 'kids.checkin.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
