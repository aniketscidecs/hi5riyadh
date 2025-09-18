from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KidsSubscriptionWizard(models.TransientModel):
    _name = 'kids.subscription.wizard'
    _description = 'Kids Subscription Wizard'

    parent_id = fields.Many2one('res.partner', string='Parent', required=True)
    child_ids = fields.Many2many('kids.child', string='Children', required=True)
    package_ids = fields.Many2many('subscription.package', string='Packages', required=True)
    
    # Bulk options
    create_pos_orders = fields.Boolean('Create POS Orders', default=True, 
                                     help='Create POS orders for all subscriptions after confirmation')
    confirm_subscriptions = fields.Boolean('Confirm Subscriptions', default=True,
                                         help='Automatically confirm all subscriptions')
    
    # Summary fields
    total_children = fields.Integer('Total Children', compute='_compute_totals')
    total_packages = fields.Integer('Total Packages', compute='_compute_totals')
    total_amount = fields.Float('Total Amount', compute='_compute_totals')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    @api.depends('child_ids', 'package_ids')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_children = len(wizard.child_ids)
            wizard.total_packages = len(wizard.package_ids)
            wizard.total_amount = sum(wizard.package_ids.mapped('price')) * len(wizard.child_ids)
    
    def action_create_subscriptions(self):
        """Create subscriptions for all selected children with selected packages"""
        self.ensure_one()
        
        if not self.child_ids:
            raise ValidationError("Please select at least one child.")
        if not self.package_ids:
            raise ValidationError("Please select at least one package.")
        
        created_subscriptions = self.env['kids.child.subscription']
        
        # Create subscription for each child
        for child in self.child_ids:
            subscription_vals = {
                'child_id': child.id,
                'package_ids': [(6, 0, self.package_ids.ids)],
                'state': 'draft',
            }
            
            subscription = self.env['kids.child.subscription'].create(subscription_vals)
            created_subscriptions |= subscription
            
            # Auto-confirm if requested
            if self.confirm_subscriptions:
                subscription.action_confirm()
        
        # Create bulk POS orders if requested
        if self.create_pos_orders and self.confirm_subscriptions:
            return self._create_bulk_pos_orders(created_subscriptions)
        
        # Show success message
        message = (
            f"Successfully created {len(created_subscriptions)} subscriptions!\n\n"
            f"Children: {', '.join(self.child_ids.mapped('name'))}\n"
            f"Packages: {', '.join(self.package_ids.mapped('name'))}\n"
            f"Total Amount: {self.total_amount:.2f} {self.currency_id.name}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Subscriptions Created Successfully',
                'message': message,
                'type': 'success',
                'sticky': True,
            }
        }
    
    def _create_bulk_pos_orders(self, subscriptions):
        """Create bulk POS orders for confirmed subscriptions"""
        # Get configured POS for subscriptions
        subscription_pos_id = self.env['ir.config_parameter'].sudo().get_param('kids_club.subscription_pos_id')
        if not subscription_pos_id:
            raise ValidationError("No POS configured for subscriptions. Please configure in Kids Club > Configuration > POS Settings.")
        
        pos_config = self.env['pos.config'].browse(int(subscription_pos_id))
        if not pos_config.exists():
            raise ValidationError("Configured subscription POS no longer exists. Please update POS Settings.")
        
        # Ensure POS session exists
        if not pos_config.current_session_id:
            session = self.env['pos.session'].create({
                'user_id': self.env.uid,
                'config_id': pos_config.id
            })
        else:
            session = pos_config.current_session_id
        
        # Create single POS order for all subscriptions
        total_amount = 0.0
        total_tax = 0.0
        
        pos_order_vals = {
            'config_id': pos_config.id,
            'session_id': session.id,
            'partner_id': self.parent_id.id,
            'pos_reference': f'BULK-SUB-{len(subscriptions)}',
            'state': 'draft',
            'amount_tax': 0.0,
            'amount_total': 0.0,
            'amount_paid': 0.0,
            'amount_return': 0.0,
        }
        
        pos_order = self.env['pos.order'].create(pos_order_vals)
        
        # Add order lines for each subscription
        for subscription in subscriptions:
            for package in subscription.package_ids:
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
                        partner=self.parent_id
                    )
                    
                    line_tax = tax_results['total_included'] - tax_results['total_excluded']
                    
                    # Create POS order line
                    self.env['pos.order.line'].create({
                        'order_id': pos_order.id,
                        'product_id': product.id,
                        'qty': 1,
                        'price_unit': price_unit,
                        'price_subtotal': tax_results['total_excluded'],
                        'price_subtotal_incl': tax_results['total_included'],
                        'full_product_name': f"{package.name} - {subscription.child_id.name}",
                        'tax_ids': [(6, 0, taxes.ids)],
                    })
                    
                    total_amount += tax_results['total_included']
                    total_tax += line_tax
        
        # Update POS order with computed totals
        pos_order.write({
            'amount_tax': total_tax,
            'amount_total': total_amount,
        })
        
        # Link POS order to all subscriptions
        for subscription in subscriptions:
            subscription.pos_order_id = pos_order.id
        
        # Show success message and open POS
        message = (
            f"Bulk POS order created successfully!\n\n"
            f"Subscriptions: {len(subscriptions)}\n"
            f"POS Order: {pos_order.pos_reference}\n"
            f"Total Amount: {total_amount:.2f} {self.currency_id.name}\n\n"
            f"Opening POS interface for payment..."
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bulk POS Order Created - Opening POS',
                'message': message,
                'type': 'success',
                'sticky': False,
                'next': pos_config.open_ui()
            }
        }
