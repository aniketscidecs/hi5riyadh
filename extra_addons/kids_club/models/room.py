from odoo import models, fields, api
from odoo.exceptions import ValidationError


class KidsRoom(models.Model):
    _name = 'kids.room'
    _description = 'Kids Club Room'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'room_number, name'

    name = fields.Char('Room Name', required=True, help="Name of the room (e.g., Play Area, Art Room)")
    room_number = fields.Char('Room Number', required=True, help="Room number or identifier")
    supervisor_id = fields.Many2one('res.users', string='Supervisor', 
                                   help="User responsible for supervising this room")
    capacity = fields.Integer('Capacity', required=True, default=10,
                             help="Maximum number of children allowed in this room")
    
    # Computed fields for current status
    current_checkins = fields.Integer('Current Check-ins', compute='_compute_current_checkins',
                                     help="Number of children currently checked in to this room")
    available_spots = fields.Integer('Available Spots', compute='_compute_available_spots',
                                    help="Number of available spots remaining")
    is_full = fields.Boolean('Room Full', compute='_compute_is_full',
                            help="True if room is at capacity")
    
    # Active field for archiving rooms
    active = fields.Boolean('Active', default=True)
    
    @api.depends('capacity')
    def _compute_current_checkins(self):
        """Compute current number of checked-in children in this room"""
        for room in self:
            checkins = self.env['kids.child.checkin'].search_count([
                ('room_id', '=', room.id),
                ('state', '=', 'checked_in')
            ])
            room.current_checkins = checkins
    
    @api.depends('capacity', 'current_checkins')
    def _compute_available_spots(self):
        """Compute available spots in the room"""
        for room in self:
            room.available_spots = room.capacity - room.current_checkins
    
    @api.depends('current_checkins', 'capacity')
    def _compute_is_full(self):
        """Check if room is at full capacity"""
        for room in self:
            room.is_full = room.current_checkins >= room.capacity
    
    @api.constrains('capacity')
    def _check_capacity(self):
        """Validate room capacity"""
        for room in self:
            if room.capacity <= 0:
                raise ValidationError("Room capacity must be greater than 0.")
    
    @api.constrains('room_number')
    def _check_unique_room_number(self):
        """Ensure room numbers are unique"""
        for room in self:
            if room.room_number:
                existing = self.search([
                    ('room_number', '=', room.room_number),
                    ('id', '!=', room.id),
                    ('active', '=', True)
                ])
                if existing:
                    raise ValidationError(f"Room number '{room.room_number}' already exists.")
    
    def name_get(self):
        """Custom display name for room selection"""
        result = []
        for room in self:
            name = f"{room.room_number} - {room.name}"
            if room.is_full:
                name += " (FULL)"
            else:
                name += f" ({room.available_spots} spots)"
            result.append((room.id, name))
        return result
    
    def check_capacity_available(self):
        """Check if room has available capacity"""
        self.ensure_one()
        return self.current_checkins < self.capacity
    
    def get_available_rooms(self):
        """Get all rooms with available capacity"""
        return self.search([
            ('active', '=', True),
            ('current_checkins', '<', self.capacity)
        ])
