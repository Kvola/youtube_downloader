#!/usr/bin/env python3
"""
Génère un icône professionnel pour YouTube Downloader.
Design : bouton play rouge avec flèche de téléchargement, fond sombre dégradé.
"""
import math
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 1024
CENTER = SIZE // 2
PADDING = int(SIZE * 0.08)


def draw_rounded_rect(draw, xy, radius, fill):
    """Dessine un rectangle avec coins arrondis."""
    x0, y0, x1, y1 = xy
    draw.rectangle([x0 + radius, y0, x1 - radius, y1], fill=fill)
    draw.rectangle([x0, y0 + radius, x1, y1 - radius], fill=fill)
    draw.pieslice([x0, y0, x0 + 2 * radius, y0 + 2 * radius], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * radius, y0, x1, y0 + 2 * radius], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * radius, x0 + 2 * radius, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * radius, y1 - 2 * radius, x1, y1], 0, 90, fill=fill)


def create_gradient_background(size):
    """Crée un fond dégradé sombre."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Dégradé du coin supérieur gauche au coin inférieur droit
    for y in range(size):
        for x in range(size):
            # Distance normalisée depuis le coin supérieur gauche
            t = (x + y) / (2 * size)
            # Couleurs : #1A1A2E → #16213E → #0F3460
            r = int(26 + (15 - 26) * t)
            g = int(26 + (47 - 26) * t)
            b = int(46 + (96 - 46) * t)
            # Only set pixel inside rounded rect area (we'll mask later)
            draw.point((x, y), fill=(r, g, b, 255))
    
    return img


def create_icon():
    """Crée l'icône principal."""
    # Image principale
    img = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # ═══ FOND ARRONDI AVEC DÉGRADÉ ═══
    corner_radius = int(SIZE * 0.22)
    
    # Créer le masque du rectangle arrondi
    mask = Image.new('L', (SIZE, SIZE), 0)
    mask_draw = ImageDraw.Draw(mask)
    draw_rounded_rect(mask_draw, [0, 0, SIZE - 1, SIZE - 1], corner_radius, 255)
    
    # Fond dégradé simplifié (bandes horizontales pour performance)
    for y in range(SIZE):
        t = y / SIZE
        # Dégradé : #1A1A2E (haut) → #0F3460 (milieu) → #1A1A2E (bas)
        if t < 0.5:
            t2 = t * 2
            r = int(26 + (15 - 26) * t2)
            g = int(26 + (52 - 26) * t2)
            b = int(46 + (96 - 46) * t2)
        else:
            t2 = (t - 0.5) * 2
            r = int(15 + (26 - 15) * t2)
            g = int(52 + (26 - 52) * t2)
            b = int(96 + (46 - 96) * t2)
        draw.line([(0, y), (SIZE - 1, y)], fill=(r, g, b, 255))
    
    img.putalpha(mask)
    
    # ═══ CERCLE ROUGE CENTRAL (bouton play) ═══
    circle_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    circle_draw = ImageDraw.Draw(circle_layer)
    
    circle_radius = int(SIZE * 0.30)
    circle_y_offset = -int(SIZE * 0.04)  # Légèrement au-dessus du centre
    cx, cy = CENTER, CENTER + circle_y_offset
    
    # Ombre du cercle
    shadow_offset = int(SIZE * 0.015)
    circle_draw.ellipse(
        [cx - circle_radius + shadow_offset, cy - circle_radius + shadow_offset * 2,
         cx + circle_radius + shadow_offset, cy + circle_radius + shadow_offset * 2],
        fill=(0, 0, 0, 80)
    )
    
    # Cercle rouge avec dégradé simulé
    # Couche externe plus foncée
    circle_draw.ellipse(
        [cx - circle_radius, cy - circle_radius,
         cx + circle_radius, cy + circle_radius],
        fill=(180, 20, 20, 255)
    )
    # Couche interne plus claire (dégradé)
    inner_r = int(circle_radius * 0.92)
    circle_draw.ellipse(
        [cx - inner_r, cy - inner_r,
         cx + inner_r, cy + inner_r],
        fill=(220, 38, 38, 255)  # #DC2626
    )
    # Reflet en haut
    highlight_r = int(circle_radius * 0.85)
    for i in range(highlight_r):
        t = i / highlight_r
        if t < 0.4:
            alpha = int(40 * (1 - t / 0.4))
            circle_draw.ellipse(
                [cx - highlight_r + i, cy - highlight_r + i,
                 cx + highlight_r - i, cy - highlight_r + i + int(highlight_r * 0.6)],
                fill=(255, 255, 255, alpha)
            )
            break  # Just one highlight layer for performance
    
    img = Image.alpha_composite(img, circle_layer)
    draw = ImageDraw.Draw(img)
    
    # ═══ TRIANGLE PLAY ═══
    # Triangle légèrement décalé à droite (convention play button)
    tri_size = int(circle_radius * 0.55)
    tri_x_offset = int(tri_size * 0.15)  # Compensation optique
    
    tri_points = [
        (cx - tri_size * 0.4 + tri_x_offset, cy - tri_size * 0.55),  # Haut gauche
        (cx - tri_size * 0.4 + tri_x_offset, cy + tri_size * 0.55),  # Bas gauche
        (cx + tri_size * 0.6 + tri_x_offset, cy),                     # Pointe droite
    ]
    draw.polygon(tri_points, fill=(255, 255, 255, 255))
    
    # ═══ FLÈCHE DE TÉLÉCHARGEMENT (en bas) ═══
    arrow_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    arrow_draw = ImageDraw.Draw(arrow_layer)
    
    arrow_top = cy + circle_radius + int(SIZE * 0.06)
    arrow_width = int(SIZE * 0.06)
    arrow_head_width = int(SIZE * 0.12)
    arrow_height = int(SIZE * 0.12)
    arrow_head_height = int(SIZE * 0.06)
    
    # Tige de la flèche
    arrow_draw.rectangle(
        [CENTER - arrow_width // 2, arrow_top,
         CENTER + arrow_width // 2, arrow_top + arrow_height - arrow_head_height],
        fill=(255, 255, 255, 230)
    )
    
    # Pointe de la flèche (triangle vers le bas)
    arrow_tip_y = arrow_top + arrow_height
    arrow_draw.polygon([
        (CENTER - arrow_head_width, arrow_top + arrow_height - arrow_head_height),
        (CENTER + arrow_head_width, arrow_top + arrow_height - arrow_head_height),
        (CENTER, arrow_tip_y + int(SIZE * 0.02)),
    ], fill=(255, 255, 255, 230))
    
    # Ligne de base (sol)
    line_y = arrow_tip_y + int(SIZE * 0.04)
    line_half_w = int(SIZE * 0.12)
    line_thickness = int(SIZE * 0.02)
    
    # Bords arrondis pour la ligne
    arrow_draw.rounded_rectangle(
        [CENTER - line_half_w, line_y,
         CENTER + line_half_w, line_y + line_thickness],
        radius=line_thickness // 2,
        fill=(255, 255, 255, 230)
    )
    
    img = Image.alpha_composite(img, arrow_layer)
    
    # ═══ PETITS ACCENTS DÉCORATIFS ═══
    accent_layer = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    accent_draw = ImageDraw.Draw(accent_layer)
    
    # Points lumineux (étoiles subtiles)
    dots = [
        (int(SIZE * 0.15), int(SIZE * 0.18), 4, 100),
        (int(SIZE * 0.85), int(SIZE * 0.15), 3, 80),
        (int(SIZE * 0.12), int(SIZE * 0.75), 3, 70),
        (int(SIZE * 0.88), int(SIZE * 0.80), 4, 90),
        (int(SIZE * 0.25), int(SIZE * 0.35), 2, 60),
        (int(SIZE * 0.78), int(SIZE * 0.42), 2, 50),
    ]
    
    for dx, dy, r, alpha in dots:
        accent_draw.ellipse(
            [dx - r, dy - r, dx + r, dy + r],
            fill=(255, 255, 255, alpha)
        )
    
    img = Image.alpha_composite(img, accent_layer)
    
    return img


def main():
    print("🎨 Génération de l'icône YouTube Downloader...")
    
    icon = create_icon()
    
    # Sauvegarder en haute résolution (1024x1024)
    output_path = "assets/images/logo.png"
    icon.save(output_path, "PNG", optimize=True)
    print(f"✅ Icône 1024x1024 sauvegardée → {output_path}")
    
    # Créer aussi une version pour l'adaptive icon (foreground sur fond transparent)
    # avec padding pour Android adaptive icon
    adaptive = Image.new('RGBA', (1024, 1024), (0, 0, 0, 0))
    # L'adaptive icon a besoin de padding (safe zone = 66% du centre)
    icon_resized = icon.resize((int(1024 * 0.70), int(1024 * 0.70)), Image.LANCZOS)
    offset = (1024 - icon_resized.width) // 2
    adaptive.paste(icon_resized, (offset, offset), icon_resized)
    adaptive.save("assets/images/icon_adaptive_foreground.png", "PNG", optimize=True)
    print(f"✅ Adaptive foreground sauvegardée → assets/images/icon_adaptive_foreground.png")
    
    print("\n📱 Pour appliquer l'icône, exécutez :")
    print("   flutter pub run flutter_launcher_icons")


if __name__ == '__main__':
    main()
