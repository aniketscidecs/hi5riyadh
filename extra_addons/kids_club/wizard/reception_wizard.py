from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class ReceptionWizard(models.TransientModel):
    _name = 'kids.reception.wizard'
    _description = 'Reception Wizard for Kids Club'
    _rec_name = 'display_name'

    # Display name field to control form title
    display_name = fields.Char('Display Name', default='Reception', readonly=True)

    # Wizard state management
    state = fields.Selection([
        ('parent_details', 'Parent Details'),
        ('kid_info', 'Kid Info'),
        ('action', 'Action'),
        ('summary', 'Summary')
    ], string='State', default='parent_details')

    # Parent Information
    parent_id = fields.Many2one('res.partner', string='Parent', domain=[('is_parent', '=', True)])
    parent_name = fields.Char('Parent Name (English)')
    parent_name_arabic = fields.Char('Parent Name (Arabic)')
    parent_mobile = fields.Char('Mobile')
    parent_emergency_mobile = fields.Char('Emergency Mobile')
    parent_identification_type = fields.Selection([
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('iqama', 'Iqama')
    ], string='Identification Type')
    parent_identification_number = fields.Char('Identification Number')
    parent_branch = fields.Char('Branch')
    parent_nationality = fields.Char('Nationality')
    parent_email = fields.Char('Email')



    # Children Information
    available_children_ids = fields.One2many('kids.child', related='parent_id.children_ids', string='Available Children', readonly=True)

    # Action Selection
    action_type = fields.Selection([
        ('purchase_packages', 'Purchase Packages'),
        ('quick_checkin', 'Quick Check-in'),
        ('quick_checkout', 'Quick Check-out')
    ], string='Action Type')

    # Package Selection (for purchase action)
    package_ids = fields.Many2many('subscription.package', string='Selected Packages')
    auto_checkin = fields.Boolean('Auto Check-in after Purchase', default=True)

    # Summary Information
    total_amount = fields.Float('Total Amount', compute='_compute_total_amount')
    summary_text = fields.Text('Summary', readonly=True)
    
    # Temporary child fields for Kids Info step
    temp_child_name_en = fields.Char('Child Name (English)')
    temp_child_name_ar = fields.Char('Child Name (Arabic)')
    temp_child_notes = fields.Text('Child Notes')
    temp_child_hijri = fields.Char('Hijri Date')
    temp_child_dob = fields.Date('Date of Birth')

    def name_get(self):
        """Override name_get to show 'Reception' instead of 'New'"""
        return [(record.id, 'Reception') for record in self]

    @api.depends('package_ids')
    def _compute_total_amount(self):
        for record in self:
            record.total_amount = sum(record.package_ids.mapped('price'))

    @api.depends('parent_id', 'child_ids', 'action_type', 'package_ids')
    def _compute_summary(self):
        for record in self:
            summary_lines = []
            if record.parent_id:
                summary_lines.append(f"Parent: {record.parent_id.name}")
            if record.child_ids:
                child_names = ', '.join(record.child_ids.mapped('name'))
                summary_lines.append(f"Children: {child_names}")
            if record.action_type:
                summary_lines.append(f"Action: {dict(record._fields['action_type'].selection)[record.action_type]}")
            if record.package_ids:
                package_names = ', '.join(record.package_ids.mapped('name'))
                summary_lines.append(f"Packages: {package_names}")
                summary_lines.append(f"Total Amount: {record.total_amount}")
            record.summary_text = '\n'.join(summary_lines)



    @api.onchange('parent_id')
    def _onchange_parent_id(self):
        if self.parent_id:
            # Fill parent details
            self.parent_name = self.parent_id.name
            self.parent_mobile = self.parent_id.mobile
            self.parent_email = self.parent_id.email
            
            # Load available children
            self.available_children_ids = self.parent_id.children_ids
        else:
            # Clear fields
            self.parent_name = False
            self.parent_mobile = False
            self.parent_email = False
            self.available_children_ids = False

    def action_next_step(self):
        """Move to next step in wizard"""
        if self.state == 'parent_details':
            if not self.parent_id and not self.parent_name:
                raise UserError("Please select or enter parent information.")
            self.state = 'kid_info'
        elif self.state == 'kid_info':
            # Allow moving to action step even without children selected
            # Validation will happen later if needed
            self.state = 'action'
        elif self.state == 'action':
            # Allow moving to summary even without action selected
            # Validation will happen on complete if needed
            self.state = 'summary'
        
        # Just return True to refresh the current form without opening new window
        return True

    def action_previous_step(self):
        """Move to previous step in wizard"""
        if self.state == 'summary':
            self.state = 'action'
        elif self.state == 'action':
            self.state = 'kid_info'
        elif self.state == 'kid_info':
            self.state = 'parent_details'
        
        # Just return True to refresh the current form without opening new window
        return True

    def action_create_parent(self):
        """Create new parent if not exists"""
        if not self.parent_name:
            raise UserError("Please enter parent name.")
        
        parent_vals = {
            'name': self.parent_name,
            'mobile': self.parent_mobile,
            'email': self.parent_email,
            'is_kids_club_parent': True,
            'is_company': False,
        }
        
        if self.parent_identification_number:
            parent_vals['vat'] = self.parent_identification_number
            
        self.parent_id = self.env['res.partner'].create(parent_vals)
        return self.action_next_step()

    def action_complete(self):
        """Complete the wizard and perform the selected action"""
        if self.action_type == 'purchase_packages':
            return self._process_package_purchase()
        elif self.action_type == 'quick_checkin':
            return self._process_quick_checkin()
        elif self.action_type == 'quick_checkout':
            return self._process_quick_checkout()

    def _process_package_purchase(self):
        """Process package purchase for selected children"""
        if not self.package_ids:
            raise UserError("No packages selected for purchase.")
        
        # Create subscriptions for each child
        subscriptions = self.env['kids.child.subscription']
        for child in self.child_ids:
            subscription_vals = {
                'child_id': child.id,
                'package_ids': [(6, 0, self.package_ids.ids)],
                'start_date': fields.Date.today(),
                'state': 'draft',
            }
            subscription = self.env['kids.child.subscription'].create(subscription_vals)
            subscriptions |= subscription
        
        # Confirm subscriptions to create POS orders
        subscriptions.action_confirm()
        
        # Auto check-in if requested
        if self.auto_checkin:
            for child in self.child_ids:
                self._create_checkin(child)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success!',
                'message': f'Packages purchased successfully for {len(self.child_ids)} children.',
                'type': 'success',
            }
        }

    def _process_quick_checkin(self):
        """Process quick check-in for selected children"""
        checked_in_count = 0
        for child in self.child_ids:
            if self._create_checkin(child):
                checked_in_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Check-in Complete!',
                'message': f'{checked_in_count} children checked in successfully.',
                'type': 'success',
            }
        }

    def _process_quick_checkout(self):
        """Process quick check-out for selected children"""
        checked_out_count = 0
        for child in self.child_ids:
            # Find active check-in
            active_checkin = self.env['kids.child.checkin'].search([
                ('child_id', '=', child.id),
                ('state', '=', 'checked_in')
            ], limit=1)
            
            if active_checkin:
                active_checkin.action_checkout()
                checked_out_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Check-out Complete!',
                'message': f'{checked_out_count} children checked out successfully.',
                'type': 'success',
            }
        }

    def _create_checkin(self, child):
        """Create check-in for a child"""
        try:
            # Check if child has active subscription
            active_subscription = self.env['kids.child.subscription'].search([
                ('child_id', '=', child.id),
                ('state', '=', 'active'),
                ('remaining_visits', '>', 0)
            ], limit=1)
            
            if not active_subscription:
                return False
            
            # Check if already checked in
            existing_checkin = self.env['kids.child.checkin'].search([
                ('child_id', '=', child.id),
                ('state', '=', 'checked_in')
            ], limit=1)
            
            if existing_checkin:
                return False
            
            # Create check-in directly (bypass OTP for reception)
            checkin_vals = {
                'child_id': child.id,
                'subscription_id': active_subscription.id,
                'checkin_time': fields.Datetime.now(),
                'state': 'checked_in',
            }
            
            self.env['kids.child.checkin'].create(checkin_vals)
            
            # Update subscription visits
            active_subscription.visits_used += 1
            
            return True
        except Exception:
            return False
    
    # Child Management Action Methods
    def action_save_child(self):
        """Save/Create new child from temporary fields"""
        if not self.temp_child_name_en:
            raise UserError("Please enter child name in English.")
        if not self.parent_id:
            raise UserError("Please select a parent first.")
        
        child_vals = {
            'name': self.temp_child_name_en,
            'parent_id': self.parent_id.id,
            'date_of_birth': self.temp_child_dob,
            'medical_notes': self.temp_child_notes,
        }
        
        # Create the child
        new_child = self.env['kids.child'].create(child_vals)
        
        # Clear temporary fields
        self.temp_child_name_en = False
        self.temp_child_name_ar = False
        self.temp_child_notes = False
        self.temp_child_hijri = False
        self.temp_child_dob = False
        
        # Refresh available children
        self.available_children_ids = self.parent_id.children_ids
        
        return True
    
    def action_quick_add_child(self):
        """Quick add child action - opens child form with parent pre-filled"""
        if not self.parent_id:
            raise UserError("Please select a parent first.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Add New Child',
            'res_model': 'kids.child',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_parent_id': self.parent_id.id,
                'dialog_size': 'medium',
            },
        }
    
    def action_view_child(self):
        """View child details in form view"""
        self.ensure_one()
        child_id = self.env.context.get('active_id')
        if not child_id:
            raise UserError("No child selected.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Child Details',
            'res_model': 'kids.child',
            'res_id': child_id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_edit_child(self):
        """Edit child details in form view"""
        self.ensure_one()
        child_id = self.env.context.get('active_id')
        if not child_id:
            raise UserError("No child selected.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Edit Child',
            'res_model': 'kids.child',
            'res_id': child_id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_manage_subscription(self):
        """Manage child subscription"""
        self.ensure_one()
        child_id = self.env.context.get('active_id')
        if not child_id:
            raise UserError("No child selected.")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Child Subscriptions',
            'res_model': 'kids.child.subscription',
            'view_mode': 'list,form',
            'domain': [('child_id', '=', child_id)],
            'context': {'default_child_id': child_id},
            'target': 'new',
        }
    
    def action_delete_child(self):
        """Delete child (with confirmation)"""
        self.ensure_one()
        child_id = self.env.context.get('active_id')
        if not child_id:
            raise UserError("No child selected.")
        
        child = self.env['kids.child'].browse(child_id)
        if not child.exists():
            raise UserError("Child not found.")
        
        # Check if child has active check-ins
        active_checkins = self.env['kids.child.checkin'].search([
            ('child_id', '=', child_id),
            ('state', '=', 'checked_in')
        ])
        
        if active_checkins:
            raise UserError(f"Cannot delete {child.name}. Child is currently checked in.")
        
        child_name = child.name
        child.unlink()
        
        # Refresh available children
        self.available_children_ids = self.parent_id.children_ids
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Child Deleted',
                'message': f'{child_name} has been deleted successfully.',
                'type': 'success',
            }
        }
    

