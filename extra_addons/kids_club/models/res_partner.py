from odoo import models, fields, api


class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    # Kids Club specific fields
    is_kids_club_parent = fields.Boolean('Is Kids Club Parent', default=False)
    children_ids = fields.One2many('kids.child', 'parent_id', string='Children')
    children_count = fields.Integer('Number of Children', compute='_compute_children_count', store=True)
    
    # Emergency contact information
    emergency_contact_name = fields.Char('Emergency Contact Name')
    emergency_contact_phone = fields.Char('Emergency Contact Phone')
    emergency_contact_relation = fields.Char('Relation to Child')
    
    # Kids Club membership information
    membership_start_date = fields.Date('Membership Start Date')
    membership_status = fields.Selection([
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended')
    ], string='Membership Status', default='active')
    
    # Communication preferences
    receive_notifications = fields.Boolean('Receive Notifications', default=True)
    preferred_communication = fields.Selection([
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('phone', 'Phone Call'),
        ('whatsapp', 'WhatsApp')
    ], string='Preferred Communication', default='email')
    
    @api.depends('children_ids')
    def _compute_children_count(self):
        """Compute the number of children for each parent"""
        for record in self:
            record.children_count = len(record.children_ids)
    
    def action_view_children(self):
        """Action to view children of this parent"""
        self.ensure_one()
        return {
            'name': f'Children of {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'kids.child',
            'view_mode': 'list,form',
            'domain': [('parent_id', '=', self.id)],
            'context': {
                'default_parent_id': self.id,
                'search_default_parent_id': self.id,
            },
            'target': 'current',
        }
    
    def action_view_subscriptions(self):
        """Action to view subscriptions for this parent's children"""
        self.ensure_one()
        subscription_ids = []
        for child in self.children_ids:
            subscription_ids.extend(child.subscription_ids.ids)
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Subscriptions for {self.name}',
            'res_model': 'kids.child.subscription',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', subscription_ids)],
            'target': 'current',
        }
    
    def action_quick_checkin(self):
        """Quick check-in action for parent's children"""
        self.ensure_one()
        
        # Get active children (not already checked in)
        active_children = self.children_ids.filtered(lambda c: not c.is_checked_in and c.active)
        
        if not active_children:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Children Available',
                    'message': 'No children available for check-in. They may already be checked in or inactive.',
                    'type': 'warning',
                }
            }
        
        if len(active_children) == 1:
            # If only one child, directly check them in
            child = active_children[0]
            return {
                'type': 'ir.actions.act_window',
                'name': f'Check-in {child.name}',
                'res_model': 'kids.child.checkin',
                'view_mode': 'form',
                'target': 'new',
                'context': {
                    'default_child_id': child.id,
                    'default_parent_id': self.id,
                },
            }
        else:
            # If multiple children, show selection
            return {
                'type': 'ir.actions.act_window',
                'name': f'Select Child for Check-in',
                'res_model': 'kids.child',
                'view_mode': 'list',
                'domain': [('id', 'in', active_children.ids)],
                'target': 'new',
                'context': {
                    'default_parent_id': self.id,
                    'quick_checkin_mode': True,
                },
            }
    
    @api.model
    def create(self, vals):
        """Override create to set is_kids_club_parent if children are added"""
        partner = super(ResPartner, self).create(vals)
        if partner.children_ids:
            partner.is_kids_club_parent = True
        return partner
    
    def write(self, vals):
        """Override write to update is_kids_club_parent status"""
        result = super(ResPartner, self).write(vals)
        for partner in self:
            if partner.children_ids and not partner.is_kids_club_parent:
                partner.is_kids_club_parent = True
            elif not partner.children_ids and partner.is_kids_club_parent:
                partner.is_kids_club_parent = False
        return result
