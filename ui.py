from fastapi.responses import JSONResponse
from pydantic import BaseModel
from nicegui import app, ui

DEFAULT_LAT = 30.9878
DEFAULT_LON = 34.9277

GLOBAL_PINS = []

PIN_CONFIG = {
    'Emergency': {'color': 'red', 'desc': 'Urgent response required.'},
    'Work': {'color': 'blue', 'desc': 'Designated job site.'},
    'Home': {'color': 'green', 'desc': 'Safe zone.'},
    'Personal': {'color': 'orange', 'desc': 'Personal waypoint.'},
    'Other': {'color': 'purple', 'desc': 'Custom bookmark.'}
}

# Added Esri Topo to the stack
MAP_STYLES = {
    '🗺️ OpenStreetMap': {'url': 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', 'opt': {'maxZoom': 19}},
    '🛰️ Esri Satellite': {'url': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', 'opt': {'maxZoom': 19}},
    '🏔️ Esri Topo': {'url': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', 'opt': {'maxZoom': 19}},
    '🌙 CartoDB Dark': {'url': 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', 'opt': {'maxZoom': 20}}
}

# ==========================================
# 1. POST API LISTENER
# ==========================================
class PinPayload(BaseModel):
    lat: float
    lon: float
    type: str = 'Other'

@app.post('/api/add_pin')
def external_post_listener(packet: PinPayload):
    safe_type = packet.type if packet.type in PIN_CONFIG else 'Other'
    new_pin = {
        'lat': packet.lat, 'lon': packet.lon, 
        'type': safe_type, 'desc': PIN_CONFIG[safe_type]['desc']
    }
    GLOBAL_PINS.append(new_pin)
    return JSONResponse(content={"status": "success", "added": new_pin})


# ==========================================
# 2. FULL-BLEED DASHBOARD UI
# ==========================================
def create_ui():
    dom = {'map': None, 'bg': None, 'trash_collector': []}
    client = {'rendered': 0}

    ui.add_head_html('''
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>body { font-family: 'Outfit', sans-serif; }</style>
    ''')

    ui.colors(primary='#0f172a', secondary='#334155', accent='#6366f1')
    dark = ui.dark_mode()

    ui.element('div').classes('min-h-screen w-full absolute inset-0 -z-10 bg-slate-50 dark:bg-slate-950')

    def change_skin(e):
        if dom['bg']: dom['map'].remove_layer(dom['bg'])
        dom['bg'] = dom['map'].tile_layer(url_template=MAP_STYLES[e.value]['url'], options=MAP_STYLES[e.value]['opt'])

    def wipe_dashboard():
        GLOBAL_PINS.clear()
        client['rendered'] = 0
        for layer_instance in dom['trash_collector']:
            dom['map'].remove_layer(layer_instance)
        dom['trash_collector'].clear()

    # --- TOP NAVBAR ---
    with ui.header().classes('bg-white/40 dark:bg-slate-900/50 backdrop-blur-md px-6 py-3 flex justify-between items-center border-b border-slate-200 dark:border-slate-800'):
        
        # Rebranded to SAR YDT
        ui.label('SAR YDT').classes('text-2xl font-bold tracking-wider text-slate-800 dark:text-white')
        
        with ui.row().classes('items-center gap-2 md:gap-4'):
            ui.button('Clear', icon='delete_outline', on_click=wipe_dashboard).props('flat color="red"').classes('font-medium')
            ui.select(options=list(MAP_STYLES.keys()), value='🗺️ OpenStreetMap', on_change=change_skin).classes('w-44 md:w-48').props('outlined dense borderless')
            ui.button(icon='dark_mode', on_click=dark.toggle).props('flat round').classes('text-slate-800 dark:text-white')

    # --- MAIN STAGE ---
    with ui.row().classes('w-full max-w-7xl mx-auto p-4 pt-20'):
        with ui.card().classes('w-full p-2 rounded-[2rem] shadow-2xl border border-slate-200 dark:border-slate-800'):
            dom['map'] = ui.leaflet(center=(DEFAULT_LAT, DEFAULT_LON), zoom=13).classes('w-full h-[720px] rounded-[1.5rem]')
            dom['bg'] = dom['map'].tile_layer(url_template=MAP_STYLES['🗺️ OpenStreetMap']['url'])

    def sync_map_to_ledger():
        while client['rendered'] < len(GLOBAL_PINS):
            p = GLOBAL_PINS[client['rendered']]
            color = PIN_CONFIG[p['type']]['color']
            
            marker = dom['map'].marker(latlng=(p['lat'], p['lon']))
            marker.run_method('bindPopup', f"<b>{p['type']}</b><br><span style='font-size:12px'>{p['desc']}</span>")
            
            circle = dom['map'].generic_layer(name='circleMarker', args=[[p['lat'], p['lon']], {'color': color, 'fillColor': color, 'fillOpacity': 0.4, 'radius': 16, 'weight': 2}])
            dom['trash_collector'].extend([marker, circle])
            
            dom['map'].set_center((p['lat'], p['lon']))
            client['rendered'] += 1

    ui.timer(0.5, sync_map_to_ledger)

create_ui()

# Browser tab text re-bound
ui.run(title="SAR YDT", favicon="📍", port=8080)