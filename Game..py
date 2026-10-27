from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import math
import random

# Camera & View
camX, camY, camZ = 0.0, 20.0, 60.0  # Global View
fpv_mode = False                    # 'V' key toggle

# Gun Control
gun_angle_x = 0.0  # A/D Rotate
gun_angle_y = 0.0  # W/S Aim

# Tower/Gun geometry
OBS_HEIGHT = 18.0
GUN_LENGTH = 4.0

# Game State
score = 0
bullets_fired = 0
base_health = 5
game_over = False
win_status = False
auto_pilot = False  # 'C' key toggle
base_hit_streak = 0  # End game if 2 consecutive hits on base/tower
auto_fire_cooldown = 0  # frames between auto shots
auto_target_id = None  # current target enemy id for cheat fire limit
auto_target_shots = 0  # shots fired at current target
frames_since_start = 0  # frame counter for startup behaviors
ALERT_DELAY_FRAMES = 120  # keep tower light green for ~2s at 60 FPS

# Objects Lists
bullets = []
enemies = []
explosions = []  # Visual feedback
muzzle_flashes = []  # Muzzle flash effect
next_enemy_id = 0  # Unique id for tracking targets

# Enemy Wave Settings
WAVE_SIZE = 5
enemy_spawn_timer = 0
ENEMY_SPAWN_RATE = 30  # Spawn a tank every 30 frames
ENEMY_SPEED = 0.08
BASE_HIT_RADIUS = 12.0  # Distance at which a tank counts as hitting the base/tower
TARGET_HIT_RADIUS = 4.5  # Direct hit threshold on tower/tents
# Primary targets: tower center and two tents
TARGET_POINTS = [(0, 0), (-15, -15), (15, -15)]
current_wave_side = None  # Track which side current wave spawns from

# Static obstacles for collision detection (x, z, radius)
OBSTACLES = [
    # Tents
    (-15, -15, 5),
    (15, -15, 5),
    # Tower (center)
    (0, 0, 6),
    # Sandbags
    (-10, 8, 3),
    (10, 8, 3),
    (-8, -8, 3),
    (8, -8, 3),
    # Crates
    (-20, 5, 2),
    (20, 5, 2),
    (18, 7, 2),
    (-12, -25, 2),
    (12, -25, 2),
    # Trees
    (-50, -50, 4), (50, -50, 4), (-50, 50, 4), (50, 50, 4),
    (-70, 0, 4), (70, 0, 4), (0, -70, 4), (0, 70, 4),
    (-40, -70, 4), (40, -70, 4), (-70, -40, 4), (70, -40, 4),
    (-70, 40, 4), (70, 40, 4), (-40, 70, 4), (40, 70, 4)
]

def calculate_distance(x1, z1, x2, z2):
    return math.sqrt((x2 - x1)**2 + (z2 - z1)**2)

def check_collision(x, z, radius=2.5):
    """Check if position (x, z) with given radius collides with any obstacle"""
    # Check against static obstacles
    for ox, oz, oradius in OBSTACLES:
        dist = calculate_distance(x, z, ox, oz)
        if dist < (radius + oradius):
            return True
    return False

def check_tank_collision(x, z, current_tank, radius=3.5):
    """Check if tank collides with other tanks or obstacles"""
    # Check against static obstacles
    if check_collision(x, z, radius):
        return True
    
    # Check against other tanks - use larger separation distance
    for e in enemies:
        if e is not current_tank:
            dist = calculate_distance(x, z, e['x'], e['z'])
            if dist < (radius * 2 + 0.5):  # Two tank radii plus buffer
                return True
    
    return False


def drawText(x, y, text):
    # HUD Text Overlay
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, 800, 0, 600)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    glColor3f(1.0, 1.0, 1.0)
    glRasterPos2f(x, y)
    for char in text:
        glutBitmapCharacter(GLUT_BITMAP_HELVETICA_18, ord(char))
        
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def drawGround():
    # Main grass ground
    glColor3f(0.13, 0.55, 0.13) # Forest Green
    glBegin(GL_QUADS)
    glVertex3f(-200, 0, -200)
    glVertex3f(200, 0, -200)
    glVertex3f(200, 0, 200)
    glVertex3f(-200, 0, 200)
    glEnd()
    
    # Dirt paths around base
    glColor3f(0.4, 0.3, 0.2) # Dirt brown
    # Main path to watchtower
    glBegin(GL_QUADS)
    glVertex3f(-3, 0.01, -30)
    glVertex3f(3, 0.01, -30)
    glVertex3f(3, 0.01, 30)
    glVertex3f(-3, 0.01, 30)
    glEnd()
    
    # Path to left tent
    glBegin(GL_QUADS)
    glVertex3f(-20, 0.01, -18)
    glVertex3f(-10, 0.01, -18)
    glVertex3f(-10, 0.01, -12)
    glVertex3f(-20, 0.01, -12)
    glEnd()
    
    # Path to right tent
    glBegin(GL_QUADS)
    glVertex3f(10, 0.01, -18)
    glVertex3f(20, 0.01, -18)
    glVertex3f(20, 0.01, -12)
    glVertex3f(10, 0.01, -12)
    glEnd()
    
    # Darker patches (worn areas)
    glColor3f(0.1, 0.4, 0.1)
    for px, pz in [(-5, -5), (5, 5), (-8, 8), (10, -10)]:
        glBegin(GL_POLYGON)
        for i in range(8):
            angle = i * 45
            rad = math.radians(angle)
            glVertex3f(px + math.cos(rad)*2, 0.01, pz + math.sin(rad)*2)
        glEnd()

def drawTent(x, z):
    glPushMatrix()
    glTranslatef(x, 0, z)
    
    # Tent Base (floor)
    glColor3f(0.3, 0.3, 0.2)
    glBegin(GL_QUADS)
    glVertex3f(-3, 0.01, -4)
    glVertex3f(3, 0.01, -4)
    glVertex3f(3, 0.01, 4)
    glVertex3f(-3, 0.01, 4)
    glEnd()
    
    # Main Tent Body
    glColor3f(0.4, 0.5, 0.4) # Army Green
    glBegin(GL_TRIANGLES)
    # Front side
    glVertex3f(0, 4.5, 0); glVertex3f(-3, 0, 4); glVertex3f(3, 0, 4)
    # Back side
    glVertex3f(0, 4.5, 0); glVertex3f(3, 0, -4); glVertex3f(-3, 0, -4)
    # Left side
    glVertex3f(0, 4.5, 0); glVertex3f(-3, 0, -4); glVertex3f(-3, 0, 4)
    # Right side
    glVertex3f(0, 4.5, 0); glVertex3f(3, 0, 4); glVertex3f(3, 0, -4)
    glEnd()
    
    # Tent door flap (front)
    glColor3f(0.35, 0.45, 0.35)
    glBegin(GL_QUADS)
    glVertex3f(-0.8, 0, 4.01)
    glVertex3f(0.8, 0, 4.01)
    glVertex3f(0.8, 2.5, 4.01)
    glVertex3f(-0.8, 2.5, 4.01)
    glEnd()
    
    # Support poles (wooden)
    glColor3f(0.4, 0.25, 0.1) # Wood brown
    for px, pz in [(-2.5, 3.5), (2.5, 3.5), (-2.5, -3.5), (2.5, -3.5)]:
        glPushMatrix()
        glTranslatef(px, 0, pz)
        gluCylinder(gluNewQuadric(), 0.1, 0.1, 4.0, 6, 1)
        glPopMatrix()
    
    # Guy ropes (tent support lines)
    glColor3f(0.6, 0.6, 0.5)
    glLineWidth(2.0)
    glBegin(GL_LINES)
    # Front ropes
    glVertex3f(-2.5, 3.5, 3.5); glVertex3f(-4, 0, 5.5)
    glVertex3f(2.5, 3.5, 3.5); glVertex3f(4, 0, 5.5)
    # Back ropes
    glVertex3f(-2.5, 3.5, -3.5); glVertex3f(-4, 0, -5.5)
    glVertex3f(2.5, 3.5, -3.5); glVertex3f(4, 0, -5.5)
    glEnd()
    glLineWidth(1.0)
    
    # Tent stakes
    glColor3f(0.3, 0.3, 0.3)
    for sx, sz in [(-4, 5.5), (4, 5.5), (-4, -5.5), (4, -5.5)]:
        glPushMatrix()
        glTranslatef(sx, 0.3, sz)
        glScalef(0.1, 0.6, 0.1)
        glutSolidCube(1.0)
        glPopMatrix()
    
    glPopMatrix()

def drawSandbags(x, z, rotation=0):
    glPushMatrix()
    glTranslatef(x, 0, z)
    glRotatef(rotation, 0, 1, 0)
    
    # Multiple sandbags stacked
    glColor3f(0.6, 0.55, 0.4) # Sandy beige
    for row in range(2):
        for i in range(4):
            glPushMatrix()
            offset = 0.4 if row == 1 else 0
            glTranslatef((i - 1.5) * 1.2 + offset, row * 0.6, 0)
            glScalef(1.0, 0.5, 0.8)
            glutSolidCube(1.0)
            glPopMatrix()
    
    glPopMatrix()

def drawCrate(x, y, z, size=1.0):
    glPushMatrix()
    glTranslatef(x, y, z)
    
    # Wooden crate
    glColor3f(0.5, 0.35, 0.2) # Wood
    glutSolidCube(size)
    
    # Crate bands (metal straps)
    glColor3f(0.3, 0.3, 0.3)
    glLineWidth(3.0)
    glBegin(GL_LINES)
    # Horizontal bands
    s = size/2
    for offset in [-0.3, 0, 0.3]:
        glVertex3f(-s, offset, s); glVertex3f(s, offset, s)
        glVertex3f(-s, offset, -s); glVertex3f(s, offset, -s)
        glVertex3f(-s, offset, -s); glVertex3f(-s, offset, s)
        glVertex3f(s, offset, -s); glVertex3f(s, offset, s)
    glEnd()
    glLineWidth(1.0)
    
    glPopMatrix()


def drawTower():
    global auto_pilot, frames_since_start, ALERT_DELAY_FRAMES
    glPushMatrix()
    glTranslatef(0, 0, 0)
    
    # Army green/olive color for structure
    tower_color = (0.42, 0.45, 0.38)
    dark_metal = (0.35, 0.37, 0.32)
    
    # Tower Base Platform
    glColor3f(*dark_metal)
    glPushMatrix()
    glTranslatef(0, 0.3, 0)
    glScalef(5.0, 0.6, 5.0)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # 4 Main Support Legs (Corner Posts) - Tall and thin
    glColor3f(*tower_color)
    leg_positions = [(-2.0, -2.0), (2.0, -2.0), (-2.0, 2.0), (2.0, 2.0)]
    for lx, lz in leg_positions:
        glPushMatrix()
        glTranslatef(lx, 0, lz)
        glScalef(0.3, 18, 0.3)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Cross Bracing (X-patterns on all 4 sides)
    glColor3f(*dark_metal)
    glLineWidth(4.0)
    
    # Front face bracing (multiple levels)
    for level in range(3):
        y_base = level * 6
        glBegin(GL_LINES)
        # X brace
        glVertex3f(-2.0, y_base, 2.0); glVertex3f(2.0, y_base + 6, 2.0)
        glVertex3f(2.0, y_base, 2.0); glVertex3f(-2.0, y_base + 6, 2.0)
        glEnd()
    
    # Back face bracing
    for level in range(3):
        y_base = level * 6
        glBegin(GL_LINES)
        glVertex3f(-2.0, y_base, -2.0); glVertex3f(2.0, y_base + 6, -2.0)
        glVertex3f(2.0, y_base, -2.0); glVertex3f(-2.0, y_base + 6, -2.0)
        glEnd()
    
    # Left face bracing
    for level in range(3):
        y_base = level * 6
        glBegin(GL_LINES)
        glVertex3f(-2.0, y_base, -2.0); glVertex3f(-2.0, y_base + 6, 2.0)
        glVertex3f(-2.0, y_base, 2.0); glVertex3f(-2.0, y_base + 6, -2.0)
        glEnd()
    
    # Right face bracing
    for level in range(3):
        y_base = level * 6
        glBegin(GL_LINES)
        glVertex3f(2.0, y_base, -2.0); glVertex3f(2.0, y_base + 6, 2.0)
        glVertex3f(2.0, y_base, 2.0); glVertex3f(2.0, y_base + 6, -2.0)
        glEnd()
    
    glLineWidth(1.0)
    
    # Intermediate Platforms (at different heights)
    glColor3f(*dark_metal)
    for platform_height in [6, 12]:
        glPushMatrix()
        glTranslatef(0, platform_height, 0)
        glScalef(4.5, 0.3, 4.5)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # External Zigzag Stairs (multiple flights)
    glColor3f(*dark_metal)
    stair_width = 1.2
    
    # First flight (bottom to first platform)
    for i in range(12):
        glPushMatrix()
        glTranslatef(2.5, i * 0.5, -2.0 + i * 0.3)
        glScalef(stair_width, 0.1, 0.4)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Second flight (first to second platform)
    for i in range(12):
        glPushMatrix()
        glTranslatef(-2.5, 6 + i * 0.5, 2.0 - i * 0.3)
        glScalef(stair_width, 0.1, 0.4)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Third flight (second platform to observation room)
    for i in range(12):
        glPushMatrix()
        glTranslatef(2.5, 12 + i * 0.5, 2.0 - i * 0.3)
        glScalef(stair_width, 0.1, 0.4)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Stair Railings
    glLineWidth(3.0)
    glColor3f(0.3, 0.3, 0.3)
    glBegin(GL_LINES)
    # First flight railing
    for i in range(12):
        glVertex3f(2.5 + 0.6, i * 0.5 + 0.5, -2.0 + i * 0.3)
        glVertex3f(2.5 + 0.6, (i + 1) * 0.5 + 0.5, -2.0 + (i + 1) * 0.3)
    glEnd()
    glLineWidth(1.0)
    
    # Top Observation Room (Half walls only, no roof)
    glColor3f(*tower_color)
    
    # Observation room floor
    glPushMatrix()
    glTranslatef(0, OBS_HEIGHT, 0)
    glScalef(4.0, 0.3, 4.0)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Only draw observation room walls if NOT in FPV mode
    if not fpv_mode:
        # Observation room half-height walls (with window cutouts)
        glColor3f(*tower_color)
        
        # Front half wall
        glPushMatrix()
        glTranslatef(0, OBS_HEIGHT + 0.5, 2.0)
        glScalef(4.0, 1.0, 0.2)
        glutSolidCube(1.0)
        glPopMatrix()
        
        # Back half wall
        glPushMatrix()
        glTranslatef(0, OBS_HEIGHT + 0.5, -2.0)
        glScalef(4.0, 1.0, 0.2)
        glutSolidCube(1.0)
        glPopMatrix()
        
        # Left half wall
        glPushMatrix()
        glTranslatef(-2.0, OBS_HEIGHT + 0.5, 0)
        glScalef(0.2, 1.0, 4.0)
        glutSolidCube(1.0)
        glPopMatrix()
        
        # Right half wall
        glPushMatrix()
        glTranslatef(2.0, OBS_HEIGHT + 0.5, 0)
        glScalef(0.2, 1.0, 4.0)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Windows (darker rectangles)
    glColor3f(0.2, 0.25, 0.3) # Dark window color
    window_positions = [
        (0, 0.3, 0, 1.5, 1.0, 0.1),  # Foundation box at base of pillar
    ]
    for wx, wy, wz, sx, sy, sz in window_positions:
        glPushMatrix()
        glTranslatef(wx, wy, wz)
        glScalef(sx, sy, sz)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Sensor Light on roof (Green = Safe, Red = Enemy within 300 units)
    ALERT_DISTANCE = 300.0
    danger = False

    # Keep light green during initial grace period
    if frames_since_start >= ALERT_DELAY_FRAMES:
        # Check distance to all enemies - only turn red when inside 300 radius
        for e in enemies:
            enemy_dist = calculate_distance(0, 0, e['x'], e['z'])
            
            # Trigger red ONLY when enemy distance is less than or equal to 300
            if enemy_dist <= ALERT_DISTANCE:
                danger = True
                break  # No need to check further

    # Set light color based on danger status
    if danger:
        glColor3f(1.0, 0.0, 0.0) # RED Light - Enemy inside 300 units!
    else:
        glColor3f(0.0, 1.0, 0.0) # GREEN Light - All clear (start or enemies outside 300)
        
    glPushMatrix()
    glTranslatef(0, OBS_HEIGHT + 3.4, 0)
    glutSolidSphere(0.4, 10, 10)
    glPopMatrix()

    # Machine Gun (Rotatable) - mounted on top/in observation room
    glPushMatrix()
    glTranslatef(0, OBS_HEIGHT + 1.5, 0) # Inside observation room
    glRotatef(gun_angle_y, 0, 1, 0) # Rotate Left/Right
    glRotatef(gun_angle_x, 1, 0, 0) # Rotate Up/Down
    
    glColor3f(0.2, 0.2, 0.2) # Black Gun
    # Gun mount (thicker base)
    glPushMatrix()
    glTranslatef(0, -0.1, 0)
    glScalef(0.6, 0.6, 0.6)
    glutSolidCube(1.0)
    glPopMatrix()

    # Mount base plate
    glPushMatrix()
    glTranslatef(0, -0.35, 0)
    glScalef(0.9, 0.2, 0.9)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Gun barrel assembly (machine gun style)
    # Barrel shroud/receiver (slimmer)
    glPushMatrix()
    glTranslatef(0, 0, 1.0)
    glScalef(0.45, 0.32, 1.5)
    glutSolidCube(1.0)
    glPopMatrix()

    # Main barrel tube (longer, thinner)
    glPushMatrix()
    glTranslatef(0, 0, 3.0)
    quad = gluNewQuadric()
    gluCylinder(quad, 0.12, 0.10, 3.0, 14, 1)
    glPopMatrix()

    # Muzzle brake (slimmer)
    glPushMatrix()
    glTranslatef(0, 0, 6.0)
    glScalef(0.24, 0.24, 0.55)
    glutSolidCube(1.0)
    glPopMatrix()

    # Simple top sight (scaled down)
    glPushMatrix()
    glTranslatef(0, 0.28, 1.1)
    glScalef(0.14, 0.14, 0.28)
    glutSolidCube(1.0)
    glPopMatrix()
    
    glPopMatrix()
    glPopMatrix()

def drawEnemy(e):
    glPushMatrix()
    glTranslatef(e['x'], 0.0, e['z'])
    # Rotate tank to face the direction it's moving
    glRotatef(e['angle'], 0, 1, 0)
    
    # Tank Treads (Left)
    glColor3f(0.2, 0.2, 0.2) # Dark Gray
    glPushMatrix()
    glTranslatef(-1.2, 0.4, 0)
    glScalef(0.4, 0.8, 3.5)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Tank Treads (Right)
    glPushMatrix()
    glTranslatef(1.2, 0.4, 0)
    glScalef(0.4, 0.8, 3.5)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Main Tank Body
    glColor3f(0.6, 0.0, 0.0) # Red Body
    glPushMatrix()
    glTranslatef(0, 1.0, 0)
    glScalef(2.2, 0.8, 3.0)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Turret Base
    glColor3f(0.5, 0.0, 0.0) # Darker Red
    glPushMatrix()
    glTranslatef(0, 1.6, 0)
    glScalef(1.5, 0.6, 1.5)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Turret Top (Rounded)
    glPushMatrix()
    glTranslatef(0, 2.0, 0)
    glScalef(1.2, 0.8, 1.2)
    glutSolidSphere(0.5, 10, 10)
    glPopMatrix()
    
    # Tank Barrel
    glColor3f(0.3, 0.3, 0.3) # Dark Gray
    glPushMatrix()
    glTranslatef(0, 2.0, 1.5) # Position at front
    gluCylinder(gluNewQuadric(), 0.15, 0.15, 2.0, 8, 1) # Barrel
    glPopMatrix()
    
    # Tank Hatch
    glColor3f(0.4, 0.0, 0.0)
    glPushMatrix()
    glTranslatef(0, 2.2, -0.3)
    glutSolidCube(0.4)
    glPopMatrix()
    
    glPopMatrix()

def drawBullet(b):
    glPushMatrix()
    glTranslatef(b['x'], b['y'], b['z'])
    glColor3f(1.0, 1.0, 0.0) # Yellow
    glutSolidSphere(0.3, 10, 10)
    
    glPopMatrix()

def drawMuzzleFlash(mf):
    glPushMatrix()
    glTranslatef(mf['x'], mf['y'], mf['z'])
    
    # Pulsing orange/yellow flash
    size = (1.0 - mf['timer'] / 5.0) * 0.8
    if size > 0:
        glColor3f(1.0, 0.7, 0.0)  # Orange
        glutSolidSphere(size, 8, 8)
        
        # Yellow core
        glColor3f(1.0, 1.0, 0.0)
        glutSolidSphere(size * 0.6, 8, 8)
    
    glPopMatrix()

def drawTree(x, z):
    glPushMatrix()
    glTranslatef(x, 0, z)
    
    # Tree Base/Roots (underground)
    glColor3f(0.3, 0.15, 0.05) # Dark brown
    glPushMatrix()
    glTranslatef(0, -0.3, 0)
    glScalef(1.2, 0.6, 1.2)
    glutSolidCube(1.0)
    glPopMatrix()
    
    # Root protrusions
    for rx, rz in [(-0.4, -0.4), (0.4, -0.4), (-0.4, 0.4), (0.4, 0.4)]:
        glPushMatrix()
        glTranslatef(rx, -0.2, rz)
        glScalef(0.3, 0.4, 0.3)
        glutSolidCube(1.0)
        glPopMatrix()
    
    # Main Tree Trunk (tapered cylinder)
    glColor3f(0.35, 0.18, 0.05) # Dark tree bark
    glPushMatrix()
    glTranslatef(0, 0, 0)
    glRotatef(-90, 1, 0, 0)  # Rotate to make trunk vertical (along Y-axis)
    
    # Lower trunk (thicker)
    quad = gluNewQuadric()
    glColor3f(0.35, 0.18, 0.05)
    gluCylinder(quad, 0.6, 0.5, 5.0, 32, 3)
    
    # Upper trunk (thinner, slight curve implied by taper)
    glTranslatef(0, 0, 5.0)
    gluCylinder(quad, 0.5, 0.3, 4.0, 32, 3)
    
    glPopMatrix()
    
    # Bark details (horizontal rings)
    glColor3f(0.25, 0.12, 0.02)
    glLineWidth(2.0)
    for ring_h in range(0, 9):
        h = ring_h * 1.0
        # Calculate correct radius to match trunk cylinders
        if h <= 5.0:
            # Lower trunk: radius from 0.6 to 0.5
            radius = 0.6 - (h / 5.0) * 0.1
        else:
            # Upper trunk: radius from 0.5 to 0.3
            radius = 0.5 - ((h - 5.0) / 4.0) * 0.2
        
        glBegin(GL_LINE_LOOP)
        for i in range(32):  # Match trunk smoothness
            angle = i * (360 / 32)
            rad = math.radians(angle)
            glVertex3f(math.cos(rad) * radius, h, math.sin(rad) * radius)
        glEnd()
    glLineWidth(1.0)
    
    # Main Foliage Canopy - Realistic layered spheres
    # Lower canopy (larger, darker)
    glColor3f(0.0, 0.5, 0.1) # Medium-dark green
    for fx, fz, size in [
        (0, 0, 3.0),
        (-0.8, -0.8, 2.2),
        (0.8, -0.8, 2.2),
        (-0.8, 0.8, 2.2),
        (0.8, 0.8, 2.2)
    ]:
        glPushMatrix()
        glTranslatef(fx, 9.5, fz)
        glutSolidSphere(size, 16, 12)
        glPopMatrix()
    
    # Mid canopy (medium, lighter)
    glColor3f(0.1, 0.6, 0.15) # Brighter green
    for fx, fz, size in [
        (0, 0, 2.5),
        (-0.5, -0.5, 1.8),
        (0.5, -0.5, 1.8),
        (-0.5, 0.5, 1.8),
        (0.5, 0.5, 1.8)
    ]:
        glPushMatrix()
        glTranslatef(fx, 11.5, fz)
        glutSolidSphere(size, 16, 12)
        glPopMatrix()
    
    # Upper canopy (smaller, brightest)
    glColor3f(0.2, 0.7, 0.2) # Light green
    for fx, fz, size in [
        (0, 0, 1.8),
        (-0.3, -0.3, 1.2),
        (0.3, -0.3, 1.2),
        (-0.3, 0.3, 1.2),
        (0.3, 0.3, 1.2)
    ]:
        glPushMatrix()
        glTranslatef(fx, 13.0, fz)
        glutSolidSphere(size, 16, 12)
        glPopMatrix()
    
    # Top crown (peak)
    glColor3f(0.3, 0.75, 0.25) # Bright top
    glPushMatrix()
    glTranslatef(0, 14.5, 0)
    glutSolidSphere(1.2, 16, 12)
    glPopMatrix()
    
    # Branch stubs (visible through foliage)
    glColor3f(0.4, 0.25, 0.1)
    glLineWidth(3.0)
    branch_points = [
        ((0, 5.5, 0), (-1.5, 7, -1.5)),
        ((0, 5.5, 0), (1.5, 7, 1.5)),
        ((0, 7, 0), (-2, 9, 0)),
        ((0, 7, 0), (2, 9, 0)),
        ((0, 8.5, 0), (-1, 10, -1.5)),
        ((0, 8.5, 0), (1.5, 10, 1)),
    ]
    glBegin(GL_LINES)
    for (x1, y1, z1), (x2, y2, z2) in branch_points:
        glVertex3f(x1, y1, z1)
        glVertex3f(x2, y2, z2)
    glEnd()
    glLineWidth(1.0)
    
    # Shadow cast on ground (subtle)
    glColor4f(0.0, 0.0, 0.0, 0.15)  # Semi-transparent black
    glBegin(GL_POLYGON)
    for i in range(16):
        angle = i * (360 / 16)
        rad = math.radians(angle)
        glVertex3f(math.cos(rad) * 3.5, 0.05, math.sin(rad) * 3.5)
    glEnd()
    
    glPopMatrix()

def drawExplosion(ex):
    # Animated explosion effect
    glPushMatrix()
    glTranslatef(ex['x'], ex['y'], ex['z'])
    
    # Pulsing orange/red sphere
    size = ex['timer'] * 0.3
    alpha = max(0, 1.0 - ex['timer'] / 20.0)
    
    glColor3f(1.0, 0.5 * alpha, 0.0)
    glutSolidSphere(size, 10, 10)
    
    glPopMatrix()

# ================= LOGIC & UPDATE =================

def spawn_enemies():
    global enemies, current_wave_side, enemy_spawn_timer, next_enemy_id
    
    def spawn_one():
        global next_enemy_id
        # Spawn inside approx 800x600 region (aligned with viewport)
        spawn_half_w = 400
        spawn_half_h = 300
        min_center_clear = 60  # avoid spawning too close to tower center

        ex, ez = 0, 0
        for _ in range(20):
            ex = random.uniform(-spawn_half_w + 20, spawn_half_w - 20)
            ez = random.uniform(-spawn_half_h + 20, spawn_half_h - 20)
            if calculate_distance(ex, ez, 0, 0) > min_center_clear:
                break

        enemies.append({'id': next_enemy_id, 'x': ex, 'z': ez, 'hp': 2, 'angle': 0}) # 2 HP per tank
        next_enemy_id += 1

    # Always maintain exactly WAVE_SIZE tanks: refill immediately when any are destroyed
    if not game_over and not win_status:
        missing = WAVE_SIZE - len(enemies)
        if missing > 0:
            for _ in range(missing):
                spawn_one()
        enemy_spawn_timer = 0

def update_bullets():
    global bullets, enemies, score, win_status, explosions, auto_target_id, auto_target_shots
    
    for b in bullets[:]:
        # Move bullet forward based on its vector
        b['x'] += b['dx']
        b['y'] += b['dy']
        b['z'] += b['dz']
        
        # Remove if too far or below ground
        if calculate_distance(0, 0, b['x'], b['z']) > 200 or b['y'] < 0:
            if b in bullets: bullets.remove(b)
            continue
            
        # Collision with Enemy - improved detection
        hit = False
        for e in enemies[:]:
            # Calculate 3D distance to enemy center
            dx = b['x'] - e['x']
            dy = b['y'] - 1.0  # Enemy center height
            dz = b['z'] - e['z']
            dist_3d = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            if dist_3d < 2.5:  # Slightly larger hit radius so any body part counts
                e['hp'] -= 1
                hit = True
                # Create explosion at hit point
                explosions.append({'x': b['x'], 'y': b['y'], 'z': b['z'], 'timer': 0})
                
                if e['hp'] <= 0:
                    enemies.remove(e)
                    score += 1
                    # Reset auto target if the destroyed enemy was targeted
                    if auto_target_id == e.get('id'):
                        auto_target_id = None
                        auto_target_shots = 0
                    # Bigger explosion for destroyed tank
                    for _ in range(2):
                        explosions.append({'x': e['x'], 'y': 1.5, 'z': e['z'], 'timer': 0})
                break
        
        if hit and b in bullets:
            bullets.remove(b)

def update_explosions():
    global explosions
    for ex in explosions[:]:
        ex['timer'] += 1
        if ex['timer'] > 20:
            explosions.remove(ex)

def update_muzzle_flashes():
    global muzzle_flashes
    for mf in muzzle_flashes[:]:
        mf['timer'] += 1
        if mf['timer'] > 5:
            muzzle_flashes.remove(mf)

def update_enemies():
    global enemies, base_health, game_over, base_hit_streak
    
    for e in enemies[:]:
        # Choose primary target: closest among tower/tents
        tx, tz = min(TARGET_POINTS, key=lambda t: calculate_distance(e['x'], e['z'], t[0], t[1]))
        dist = calculate_distance(tx, tz, e['x'], e['z'])

        # If within hit radius, register hit and end immediately
        if dist <= BASE_HIT_RADIUS:
            enemies.remove(e)
            base_health -= 1
            base_hit_streak += 1
            game_over = True  # immediate loss when a tank reaches the base/tents
            if base_hit_streak > 2:
                base_hit_streak = 2
            continue

        # Move toward target
        dx = (tx - e['x']) / dist
        dz = (tz - e['z']) / dist

        # Calculate angle to point barrel in direction of movement
        e['angle'] = math.degrees(math.atan2(dx, dz))
        
        # Calculate new position
        new_x = e['x'] + dx * ENEMY_SPEED
        new_z = e['z'] + dz * ENEMY_SPEED
        
        # Check collision with objects and other tanks
        collision_detected = check_tank_collision(new_x, new_z, e)

        # Allow push-through when near target to avoid getting stuck
        if collision_detected and dist <= TARGET_HIT_RADIUS * 1.5:
            collision_detected = False
            new_x = e['x'] + dx * ENEMY_SPEED
            new_z = e['z'] + dz * ENEMY_SPEED

        # If collision, try alternate paths
        if collision_detected:
            best_path = None
            best_distance = float('inf')
            for angle_offset in [-90, -75, -60, -45, -30, -15, 15, 30, 45, 60, 75, 90]:
                angle_rad = math.atan2(dz, dx) + math.radians(angle_offset)
                test_dx = math.cos(angle_rad)
                test_dz = math.sin(angle_rad)
                test_x = e['x'] + test_dx * ENEMY_SPEED
                test_z = e['z'] + test_dz * ENEMY_SPEED
                if not check_tank_collision(test_x, test_z, e):
                    new_dist = calculate_distance(tx, tz, test_x, test_z)
                    penalty = abs(angle_offset) * 0.1
                    score = new_dist + penalty
                    if score < best_distance:
                        best_distance = score
                        best_path = (test_x, test_z)
            if best_path is not None:
                e['x'], e['z'] = best_path
        else:
            e['x'] = new_x
            e['z'] = new_z

def auto_pilot_logic():
    global gun_angle_y, gun_angle_x, auto_fire_cooldown
    global auto_target_id, auto_target_shots
    if not enemies:
        auto_target_id = None
        auto_target_shots = 0
        return

    # Lock onto an existing target if it is still alive; otherwise pick nearest
    current_target = next((e for e in enemies if e.get('id') == auto_target_id), None)
    if current_target is None:
        current_target = min(enemies, key=lambda e: calculate_distance(0, 0, e['x'], e['z']))
        auto_target_id = current_target.get('id')
        auto_target_shots = 0

    # Aim at enemy body center
    target_y = 1.0  # approximate tank body height
    gun_origin_y = OBS_HEIGHT + 1.5
    dx = current_target['x']
    dz = current_target['z']
    dy = target_y - gun_origin_y

    # Desired yaw/pitch
    desired_yaw = math.degrees(math.atan2(dx, dz))
    planar_dist = math.hypot(dx, dz)
    desired_pitch = math.degrees(math.atan2(-dy, planar_dist))  # negative to look down

    # Smoothly step toward target angles
    def step_toward(current, target, step):
        if current < target - step:
            return current + step
        if current > target + step:
            return current - step
        return target

    yaw_step = 1.0
    pitch_step = 0.8
    gun_angle_y = step_toward(gun_angle_y, desired_yaw, yaw_step)
    gun_angle_x = step_toward(gun_angle_x, desired_pitch, pitch_step)

    # Compute current barrel direction vector
    rad_y = math.radians(gun_angle_y)
    rad_x = math.radians(gun_angle_x)
    dir_y = math.sin(-rad_x)
    hz = math.cos(-rad_x)
    dir_x = math.sin(rad_y) * hz
    dir_z = math.cos(rad_y) * hz

    # Alignment checks for near-zero miss chance
    yaw_error = abs(gun_angle_y - desired_yaw)
    pitch_error = abs(gun_angle_x - desired_pitch)
    tight_angles = yaw_error < 0.25 and pitch_error < 0.25  # stricter than before

    # Distance from target center to barrel ray (perpendicular distance)
    vt_x, vt_y, vt_z = dx, dy, dz
    cx = dir_y * vt_z - dir_z * vt_y
    cy = dir_z * vt_x - dir_x * vt_z
    cz = dir_x * vt_y - dir_y * vt_x
    perp_distance = math.sqrt(cx*cx + cy*cy + cz*cz)  # |dir| is ~1
    hit_radius = 1.5  # tighter than collision radius to avoid misses

    # Forward-facing check to ensure we are aiming toward the target
    vt_len = math.sqrt(vt_x*vt_x + vt_y*vt_y + vt_z*vt_z)
    dot = (dir_x*vt_x + dir_y*vt_y + dir_z*vt_z) / vt_len if vt_len else 0
    forward_enough = dot > math.cos(math.radians(0.35))  # ~0.35 deg cone

    aligned = tight_angles and perp_distance <= hit_radius and forward_enough
    clear_line = planar_dist < 200  # keep within reliable range

    # Cooldown to prevent spamming bullets
    if auto_fire_cooldown > 0:
        auto_fire_cooldown -= 1

    if aligned and clear_line and auto_fire_cooldown <= 0 and auto_target_shots < 2:
        shoot_bullet()
        auto_fire_cooldown = 10  # slightly longer to re-verify alignment
        auto_target_shots += 1

def update_gun_from_input():
    """Manual gun control handled on key press; no continuous polling needed."""
    if auto_pilot:
        return

def game_logic():
    global win_status, game_over
    if not game_over and not win_status:
        spawn_enemies()
        update_bullets()
        update_enemies()
        update_explosions()
        update_muzzle_flashes()
        
        if auto_pilot:
            auto_pilot_logic()
            
        # Win/Lose Condition: destroy 5 tanks within 20 bullets
        if score >= 5:
            win_status = True
        elif bullets_fired >= 20 and score < 5:
            # Out of bullets before 5 kills - game over
            game_over = True 

# ================= INPUT HANDLING =================

def shoot_bullet():
    global bullets, bullets_fired, muzzle_flashes
    if game_over or win_status or bullets_fired >= 20: return
    
    bullets_fired += 1
    
    # Calculate bullet direction based on gun angles
    rad_y = math.radians(gun_angle_y)
    rad_x = math.radians(gun_angle_x)
    
    # Vector math for 3D direction
    dy = math.sin(-rad_x)
    hz = math.cos(-rad_x) # horizontal component
    dx = math.sin(rad_y) * hz
    dz = math.cos(rad_y) * hz

    # Normalize direction
    length = math.sqrt(dx*dx + dy*dy + dz*dz)
    if length == 0:
        return
    dx /= length
    dy /= length
    dz /= length
    
    speed = 3.0  # Increased bullet speed for better gameplay
    
    # Start bullet from gun mount (aligned with FPV reticle center)
    start_x = 0.0
    start_z = 0.0
    start_y = OBS_HEIGHT + 1.5  # Gun center height / FPV eye
    
    bullets.append({
        'x': start_x, 'y': start_y, 'z': start_z,
        'dx': dx * speed, 'dy': dy * speed, 'dz': dz * speed,
        'trail': []  # (unused) kept for compatibility
    })
    
    # Add muzzle flash effect
    muzzle_flashes.append({
        'x': start_x, 'y': start_y, 'z': start_z,
        'timer': 0,
        'dx': dx, 'dy': dy, 'dz': dz
    })

def restart_game():
    global score, bullets_fired, base_health, game_over, win_status
    global bullets, enemies, explosions, gun_angle_y, gun_angle_x, auto_pilot
    global base_hit_streak, auto_fire_cooldown, auto_target_id, auto_target_shots, next_enemy_id
    global frames_since_start
    
    score = 0
    bullets_fired = 0
    base_health = 5
    game_over = False
    win_status = False
    auto_pilot = False
    base_hit_streak = 0
    auto_fire_cooldown = 0
    auto_target_id = None
    auto_target_shots = 0
    next_enemy_id = 0
    frames_since_start = 0
    gun_angle_y = 0.0
    gun_angle_x = 0.0
    bullets = []
    enemies = []
    explosions = []
    print("Game Restarted!")

def keyboard(key, x, y):
    global fpv_mode, auto_pilot, gun_angle_y, gun_angle_x
    
    key = key.decode("utf-8").lower()

    # Single-step manual aim adjustments
    yaw_step = 1.0
    pitch_step = 0.7
    if key == 'a': gun_angle_y += yaw_step
    if key == 'd': gun_angle_y -= yaw_step
    if key == 'w': gun_angle_x -= pitch_step
    if key == 's': gun_angle_x += pitch_step
    
    # Camera Toggle
    if key == 'v': fpv_mode = not fpv_mode
    
    # Auto Pilot
    if key == 'c': auto_pilot = not auto_pilot
    
    # Restart Game
    if key == 'r': restart_game()
    
    glutPostRedisplay()

def mouse(button, state, x, y):
    """Handle mouse clicks for shooting"""
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        shoot_bullet()
        glutPostRedisplay()

def specialKeys(key, x, y):
    global camX, camZ
    # [Source 24] Camera Movement
    step = 2.0
    if key == GLUT_KEY_UP: camZ -= step
    if key == GLUT_KEY_DOWN: camZ += step
    if key == GLUT_KEY_LEFT: camX -= step
    if key == GLUT_KEY_RIGHT: camX += step
    glutPostRedisplay()


def display():
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    
    # Set viewport and projection (fixed size)
    glViewport(0, 0, 800, 600)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(45, 800/600, 1, 300)
    glMatrixMode(GL_MODELVIEW)
    
    # Camera Logic
    if fpv_mode:
        # First Person View - camera at tower observation room
        rad_y = math.radians(gun_angle_y)
        rad_x = math.radians(gun_angle_x)

        # Direction vector based on gun angles
        dy = math.sin(-rad_x)
        hz = math.cos(-rad_x)
        dx = math.sin(rad_y) * hz
        dz = math.cos(rad_y) * hz

        # Camera at tower observation room
        cam_x = 0
        cam_y = OBS_HEIGHT + 1.5
        cam_z = 0

        # Look target far along barrel direction
        target_x = cam_x + dx * 200
        target_y = cam_y + dy * 200
        target_z = cam_z + dz * 200

        gluLookAt(cam_x, cam_y, cam_z,
                  target_x, target_y, target_z,
                  0, 1, 0)
    else:
        # Global View
        gluLookAt(camX, camY, camZ,  0, 5, 0,  0, 1, 0)
    
    # Draw Scene
    drawGround()
    if not fpv_mode:
        drawTower()
    
    # Post at top of tower pointing upward (thicker base)
    glColor3f(0.5, 0.35, 0.15)  # Wood/brown color

    # Base plate under post
    glPushMatrix()
    glTranslatef(0, OBS_HEIGHT + 0.05, 0)
    glScalef(1.2, 0.15, 1.2)
    glutSolidCube(1.0)
    glPopMatrix()

    # Post itself
    glPushMatrix()
    glTranslatef(0, OBS_HEIGHT + 0.2, 0)
    glRotatef(-90, 1, 0, 0)  # Rotate to point upward (along Y-axis)
    gluCylinder(gluNewQuadric(), 0.45, 0.45, 3.0, 10, 1)
    glPopMatrix()
    
    drawTent(-15, -15)
    drawTent(15, -15)
    
    # Sandbag defensive positions
    drawSandbags(-10, 8, 0)
    drawSandbags(10, 8, 0)
    drawSandbags(-8, -8, 90)
    drawSandbags(8, -8, 90)
    
    # Military crates (supplies)
    drawCrate(-20, 0.6, 5, 1.2)
    drawCrate(-20, 1.8, 5, 1.2) # Stacked
    drawCrate(20, 0.6, 5, 1.2)
    drawCrate(18, 0.6, 7, 1.0)
    drawCrate(-12, 0.5, -25, 1.0)
    drawCrate(12, 0.5, -25, 1.0)
    
    # 4 posts at camp boundaries
    corner_positions = [(-30, -30), (-30, 30), (30, -30), (30, 30)]
    glColor3f(0.5, 0.35, 0.15)  # Wood/brown color for posts
    for cx, cz in corner_positions:
        # Draw corner post (wooden pole aligned to z-axis)
        glPushMatrix()
        glTranslatef(cx, 2.5, cz)
        glRotatef(90, 1, 0, 0)  # Rotate to align with z-axis
        gluCylinder(gluNewQuadric(), 0.4, 0.4, 5.0, 8, 1)
        glPopMatrix()
    
    # Draw Trees around the perimeter (outside fence)
    tree_positions = [
        (-50, -50), (50, -50), (-50, 50), (50, 50),
        (-70, 0), (70, 0), (0, -70), (0, 70),
        (-40, -70), (40, -70), (-70, -40), (70, -40),
        (-70, 40), (70, 40), (-40, 70), (40, 70)
    ]
    for tx, tz in tree_positions:
        drawTree(tx, tz)
    
    # Draw Dynamic Objects
    for e in enemies: drawEnemy(e)
    for b in bullets: drawBullet(b)
    for ex in explosions: drawExplosion(ex)
    for mf in muzzle_flashes: drawMuzzleFlash(mf)
    
    # Draw gun barrel in FPV mode for visual reference
    if fpv_mode:
        rad_y = math.radians(gun_angle_y)
        rad_x = math.radians(gun_angle_x)
        dy = math.sin(-rad_x)
        hz = math.cos(-rad_x)
        dx = math.sin(rad_y) * hz
        dz = math.cos(rad_y) * hz

        glPushMatrix()
        # Position barrel origin at gun mount
        glTranslatef(0, OBS_HEIGHT + 1.5, 0)
        # Align to barrel direction
        glRotatef(gun_angle_y, 0, 1, 0)
        glRotatef(gun_angle_x, 1, 0, 0)

        # Draw only a thin barrel line
        glColor3f(0.2, 0.2, 0.2)
        glLineWidth(3.0)
        glBegin(GL_LINES)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, 8)  # Barrel extends forward
        glEnd()
        glLineWidth(1.0)

        # Crosshair reticle (smaller)
        glColor3f(0.0, 1.0, 0.0)
        glLineWidth(1.2)
        glBegin(GL_LINES)
        glVertex3f(-0.25, 0, 8)
        glVertex3f(0.25, 0, 8)
        glVertex3f(0, -0.25, 8)
        glVertex3f(0, 0.25, 8)
        glEnd()
        glLineWidth(1.0)

        glPopMatrix()
    
    # UI / HUD
    info = f"Tanks Destroyed: {score}/5 | Bullets: {bullets_fired}/10"
    if auto_pilot: info += " | [AUTO-PILOT ACTIVE]"
    if game_over: info = "GAME LOSE! Press R to Restart"
    if win_status: info = "MISSION ACCOMPLISHED! Press R to Restart"
    
    drawText(10, 570, info)
    
    # Additional game state messages
    if not fpv_mode and not game_over and not win_status:
        drawText(10, 20,"Controls: WASD=Aim | LEFT CLICK=Shoot | V=FPV | C=Auto-Pilot | R=Restart")
    
    glutSwapBuffers()

def timer(value):
    global frames_since_start
    frames_since_start += 1
    game_logic()
    glutPostRedisplay()
    glutTimerFunc(16, timer, 0) # ~60 FPS

def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(800, 600)
    glutCreateWindow(b"Army Base Defense 3D")   
    glEnable(GL_DEPTH_TEST)   
    glutDisplayFunc(display)
    glutKeyboardFunc(keyboard)
    glutSpecialFunc(specialKeys)
    glutMouseFunc(mouse)
    glutTimerFunc(0, timer, 0)
    
    glutMainLoop()

if __name__ == "__main__":
    main()