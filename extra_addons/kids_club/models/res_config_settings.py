from odoo import models, fields, api


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # POS Configuration for Kids Club - simplified with Many2one fields
    kids_club_subscription_pos_id = fields.Many2one(
        'pos.config',
        string='Subscription POS',
        help='Select POS terminal for selling subscription packages',
        config_parameter='kids_club.subscription_pos_id'
    )
    
    kids_club_canteen_pos_id = fields.Many2one(
        'pos.config',
        string='Canteen POS',
        help='Select POS terminal for canteen sales',
        config_parameter='kids_club.canteen_pos_id'
    )


