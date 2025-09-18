from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime


class BulkCheckinWizard(models.TransientModel):
    _name = 'kids.bulk.checkin.wizard'
    _description = 'Bulk Check-in Wizard'

    child_ids = fields.Many2many(
        'kids.child', 
        string='Children to Check-in',
        required=True,
        help='Select children to check-in'
    )
    checkin_time = fields.Datetime(
        'Check-in Time', 
        default=fields.Datetime.now,
        required=True
    )
    notes = fields.Text('Notes', help='Optional notes for all check-ins')
    
    @api.model
    def default_get(self, fields_list):
        """Set default children from context"""
        res = super().default_get(fields_list)
        
        # Get child_ids from context
        if self.env.context.get('default_child_ids'):
            res['child_ids'] = self.env.context['default_child_ids']
        elif self.env.context.get('active_ids'):
            # Filter only eligible children (active and not checked in)
            active_children = self.env['kids.child'].browse(self.env.context['active_ids'])
            eligible_children = active_children.filtered(lambda c: not c.is_checked_in and c.active)
            res['child_ids'] = [(6, 0, eligible_children.ids)]
            
        return res

    def action_bulk_checkin(self):
        """Perform bulk check-in for selected children"""
        if not self.child_ids:
            raise ValidationError("Please select at least one child to check-in.")
        
        # Filter only eligible children
        eligible_children = self.child_ids.filtered(lambda c: not c.is_checked_in and c.active)
        
        if not eligible_children:
            raise ValidationError("No eligible children selected. Children must be active and not already checked in.")
        
        # Create check-in records for all eligible children
        checkin_records = []
        for child in eligible_children:
            # Check if child has active subscription
            if not child.current_subscription_id or not child.current_subscription_id.is_active:
                continue  # Skip children without active subscriptions
                
            checkin_vals = {
                'child_id': child.id,
                'checkin_time': self.checkin_time,
                'notes': self.notes or '',
                'state': 'checked_in',
            }
            checkin_record = self.env['kids.child.checkin'].create(checkin_vals)
            checkin_records.append(checkin_record)
        
        if not checkin_records:
            raise ValidationError("No children could be checked in. Please ensure they have active subscriptions.")
        
        # Show success notification
        message = f"Successfully checked in {len(checkin_records)} children:\n"
        message += "\n".join([f"• {record.child_id.name}" for record in checkin_records])
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk Check-in Successful',
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }
