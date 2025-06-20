import pygame
import cv2
from cvzone.HandTrackingModule import HandDetector
import sys
import math
import random
import speech_recognition as sr
import threading
import pyautogui


# Constants
WIDTH, HEIGHT = 800, 600
CELL_SIZE = 32
ROWS, COLS = HEIGHT // CELL_SIZE, WIDTH // CELL_SIZE
ROBOT_RADIUS = 10
SPEED = 5
EASING = 0.2

# Initialize
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Gesture + Voice + Keyboard Robot")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 28)

# Webcam and Detector
cap = cv2.VideoCapture(0)
detector = HandDetector(detectionCon=0.8, maxHands=1)

# Global state
robot_x, robot_y = CELL_SIZE + CELL_SIZE // 2, CELL_SIZE + CELL_SIZE // 2
vx = vy = 0
target_dx = target_dy = 0
current_command = "Idle"
goal_reached = False
control_mode = "hybrid"
maze_walls = []
goal_rect = pygame.Rect(WIDTH - CELL_SIZE * 2, HEIGHT - CELL_SIZE * 2, CELL_SIZE, CELL_SIZE)
score = 100
start_ticks = pygame.time.get_ticks()

# Show Start Instructions
def show_start_screen():
    screen.fill((10, 10, 10))
    instructions = [
        "Gesture-Controlled Maze Robot",
        "",
        "Controls:",
        " - Point your index finger: Up/Down/Left/Right",
        " - Or use W/A/S/D keys",
        " - Or speak: forward, back, left, right, stop",
        "",
        "Obstacles can be placed with mouse click.",
        "Reach the green GOAL box to win.",
        "",
        "Press ENTER to start..."
    ]
    for i, line in enumerate(instructions):
        text = font.render(line, True, (255, 255, 255))
        screen.blit(text, (40, 40 + i * 30))
    pygame.display.update()
    while True:
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                return
            elif event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

# Generate Maze
def generate_maze(rows, cols):
    maze = [[1 for _ in range(cols)] for _ in range(rows)]

    def carve(x, y):
        maze[y][x] = 0
        dirs = [(2, 0), (-2, 0), (0, 2), (0, -2)]
        random.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = x + dx, y + dy
            if 1 <= nx < cols - 1 and 1 <= ny < rows - 1 and maze[ny][nx] == 1:
                maze[ny - dy // 2][nx - dx // 2] = 0
                carve(nx, ny)

    carve(1, 1)
    return maze

def convert_maze_to_walls(maze):
    walls = []
    for y in range(len(maze)):
        for x in range(len(maze[0])):
            if maze[y][x] == 1:
                walls.append(pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))
    return walls

# Voice Command Thread
def voice_listener():
    global current_command, target_dx, target_dy
    r = sr.Recognizer()
    mic = sr.Microphone()
    with mic as source:
        r.adjust_for_ambient_noise(source)
    while True:
        try:
            with mic as source:
                audio = r.listen(source, timeout=5)
                command = r.recognize_google(audio).lower()
                if "forward" in command:
                    current_command = "Move Forward"
                    target_dx, target_dy = 0, -SPEED
                elif "back" in command:
                    current_command = "Move Backward"
                    target_dx, target_dy = 0, SPEED
                elif "left" in command:
                    current_command = "Turn Left"
                    target_dx, target_dy = -SPEED, 0
                elif "right" in command:
                    current_command = "Turn Right"
                    target_dx, target_dy = SPEED, 0
                elif "stop" in command:
                    current_command = "Stopped"
                    target_dx = target_dy = 0
        except:
            continue

# === Run Setup ===
show_start_screen()
maze_grid = generate_maze(ROWS, COLS)

# Find a valid goal position far from start (1,1)
for y in reversed(range(ROWS)):
    for x in reversed(range(COLS)):
        if maze_grid[y][x] == 0:
            goal_rect = pygame.Rect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE)
            break
    else:
        continue
    break
maze_walls = convert_maze_to_walls(maze_grid)

# Start voice thread
threading.Thread(target=voice_listener, daemon=True).start()

# === Main Loop ===
while True:
    screen.fill((30, 30, 30))
    success, img = cap.read()
    if not success or img is None:
        continue  # skip this frame
    img = cv2.flip(img, 1)
    hands, img = detector.findHands(img, flipType=False)
    keys = pygame.key.get_pressed()

    if not goal_reached:
        # Gesture control
        if hands and control_mode in ["gesture", "hybrid"]:
            hand = hands[0]
            lmList = hand["lmList"]
            fingers = detector.fingersUp(hand)
            if len(lmList) >= 9 and fingers.count(1) < 4:
                tip_x, tip_y = lmList[8][0], lmList[8][1]
                base_x, base_y = lmList[5][0], lmList[5][1]
                dx = tip_x - base_x
                dy = tip_y - base_y
                if abs(dx) > abs(dy):
                    if dx > 15:
                        current_command = "Turn Right"
                        target_dx, target_dy = SPEED, 0
                    elif dx < -15:
                        current_command = "Turn Left"
                        target_dx, target_dy = -SPEED, 0
                else:
                    if dy < -15:
                        current_command = "Move Backward"
                        target_dx, target_dy = 0, -SPEED
                    elif dy > 15:
                        current_command = "Move Forward"
                        target_dx, target_dy = 0, SPEED
            elif fingers.count(1) >= 4:
                current_command = "Stopped"
                target_dx = target_dy = 0

        # Keyboard control
        if control_mode in ["keyboard", "hybrid"]:
            if keys[pygame.K_w]:
                current_command = "Move Forward"
                target_dx, target_dy = 0, -SPEED
            elif keys[pygame.K_s]:
                current_command = "Move Backward"
                target_dx, target_dy = 0, SPEED
            elif keys[pygame.K_a]:
                current_command = "Turn Left"
                target_dx, target_dy = -SPEED, 0
            elif keys[pygame.K_d]:
                current_command = "Turn Right"
                target_dx, target_dy = SPEED, 0
            elif keys[pygame.K_SPACE]:
                current_command = "Stopped"
                target_dx = target_dy = 0

    # Easing motion
    vx += (target_dx - vx) * EASING
    vy += (target_dy - vy) * EASING
    next_x, next_y = int(robot_x + vx), int(robot_y + vy)

    def collides(x, y):
        rect = pygame.Rect(x - ROBOT_RADIUS, y - ROBOT_RADIUS, ROBOT_RADIUS * 2, ROBOT_RADIUS * 2)
        return any(w.colliderect(rect) for w in maze_walls)

    if not collides(next_x, next_y):
        robot_x, robot_y = next_x, next_y
    else:
        vx = vy = 0

    if goal_rect.collidepoint(robot_x, robot_y):
        goal_reached = True
        current_command = "🎯 GOAL REACHED!"
        vx = vy = target_dx = target_dy = 0

    # Draw maze
    for wall in maze_walls:
        pygame.draw.rect(screen, (100, 100, 100), wall)

    # Draw goal
    pygame.draw.rect(screen, (0, 200, 0), goal_rect)

    # Draw robot
    pygame.draw.circle(screen, (255, 0, 0), (robot_x, robot_y), ROBOT_RADIUS)

    # Score (based on time)
    if not goal_reached:
        seconds_elapsed = (pygame.time.get_ticks() - start_ticks) // 1000
        score = max(0, 100 - seconds_elapsed)

    score_text = font.render(f"Score: {score}/100", True, (255, 255, 255))
    screen.blit(score_text, (10, 10))

    if goal_reached:
        win_text = font.render("🎯 GOAL REACHED! Press R to restart", True, (0, 255, 0))
        final_score_text = font.render(f"Final Score: {score}/100", True, (255, 255, 0))
        screen.blit(win_text, (WIDTH // 2 - 150, HEIGHT // 2))
        screen.blit(final_score_text, (WIDTH // 2 - 90, HEIGHT // 2 + 40))

    pygame.display.update()
    screen_width, screen_height = pyautogui.size()
    small_img = cv2.resize(img, (320, 240))
    x = screen_width - 320
    y = screen_height - 240
    cv2.imshow("Webcam", small_img)
    cv2.moveWindow("Webcam", x, y)

    # Events
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            cap.release()
            pygame.quit()
            sys.exit()
        elif goal_reached and event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            robot_x, robot_y = CELL_SIZE + CELL_SIZE // 2, CELL_SIZE + CELL_SIZE // 2
            goal_reached = False
            vx = vy = target_dx = target_dy = 0
            current_command = "Idle"
            maze_grid = generate_maze(ROWS, COLS)
            maze_walls = convert_maze_to_walls(maze_grid)
            score = 100
            start_ticks = pygame.time.get_ticks()

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
pygame.quit()
