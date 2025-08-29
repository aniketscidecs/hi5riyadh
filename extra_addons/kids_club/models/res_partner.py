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
