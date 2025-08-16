import json
import logging
import smtplib
import subprocess
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import folium
import pandas as pd

# Sett opp basismappe
BASE_DIR = Path(__file__).parent.parent
LOG_DIR = BASE_DIR / 'logs'
DATA_DIR = BASE_DIR / 'data'
CONFIG_FILE = BASE_DIR / 'config' / 'test_config.json'
CUSTOMERS_FILE = DATA_DIR / 'raw' / 'customers.csv'
WEEKLY_ORDERS_FILE = DATA_DIR / 'raw' / 'weekly_orders.csv'

# Opprett nødvendige mapper
LOG_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Sett opp logging
log_file = LOG_DIR / 'plow_planning.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def load_config():
    """Last inn konfigurasjon fra JSON-fil."""
    try:
        logger.info(f"Prøver å laste konfigurasjon fra {CONFIG_FILE}")
        with open(CONFIG_FILE) as f:
            config = json.load(f)
        logger.info("Konfigurasjon lastet")
        return config
    except Exception as e:
        logger.error(f"Kunne ikke laste konfigurasjonsfil: {str(e)}")
        raise


def load_customers():
    """Last inn kundedata fra CSV-fil."""
    try:
        logger.info(f"Prøver å laste kundedata fra {CUSTOMERS_FILE}")
        df = pd.read_csv(CUSTOMERS_FILE)
        logger.info(f"Lastet {len(df)} kunder fra customers.csv")
        return df
    except Exception as e:
        logger.error(f"Feil ved lasting av kundedata: {str(e)}")
        return None


def load_weekly_orders():
    """Last inn ukentlige bestillinger fra CSV-fil."""
    try:
        logger.info(f"Prøver å laste ukentlige bestillinger fra {WEEKLY_ORDERS_FILE}")
        if not WEEKLY_ORDERS_FILE.exists():
            logger.error("Finner ikke weekly_orders.csv")
            return None

        # Les CSV-fil
        orders_df = pd.read_csv(WEEKLY_ORDERS_FILE)

        logger.info(f"Lastet {len(orders_df)} ukentlige bestillinger")
        return orders_df

    except Exception as e:
        logger.error(f"Feil ved lasting av ukentlige bestillinger: {str(e)}")
        return None


def get_plowing_list(customers_df, orders_df, target_date):
    """Generer liste over tun som skal brøytes på gitt dato."""
    try:
        logger.info(f"Genererer brøyteliste for {target_date}")

        # Konverter target_date til datetime hvis det er en streng
        if isinstance(target_date, str):
            target_date = pd.to_datetime(target_date)

        # Initialiser tom liste for brøyting
        plow_list = []

        # Legg til årsabonnement (uavhengig av dag)
        logger.info("Legger til årsabonnenter")
        annual_customers = customers_df[
            customers_df['Subscription'] == 'star_white'
        ]
        plow_list.extend(annual_customers.to_dict('records'))
        logger.info(f"La til {len(annual_customers)} årsabonnenter")

        # Legg til ukentlige bestillinger fra orders_df
        if not orders_df.empty:
            logger.info("Behandler ukentlige bestillinger")
            # Konverter customer_id til string i customers_df
            customers_df['customer_id'] = customers_df['customer_id'].astype(str)

            # Filtrer ut bare ukentlige bestillinger
            current_orders = orders_df[
                orders_df['abonnement_type'] == 'Ukentlig ved bestilling'
            ]

            # Hent kundeinfo for bestilte kunder
            weekly_customers = customers_df[
                customers_df['customer_id'].isin(current_orders['customer_id'].astype(str))
            ]
            # Marker disse som ukentlige bestillinger
            weekly_list = weekly_customers.to_dict('records')
            for customer in weekly_list:
                customer['Subscription'] = 'star_red'  # Endre til rød markør
            plow_list.extend(weekly_list)
            logger.info(f"La til {len(weekly_list)} ukentlige bestillinger")

        logger.info(f"Totalt {len(plow_list)} tun i brøytelisten")
        return plow_list

    except Exception as e:
        logger.error(f"Feil ved generering av brøyteliste: {str(e)}")
        return None


def create_plow_map(plow_list, target_date):
    """Lag kart med markører for tun som skal brøytes."""
    try:
        logger.info("Oppretter kart")
        if not plow_list:
            logger.error("Ingen tun å vise på kartet")
            return None, None

        # Konverter liste til DataFrame
        df = pd.DataFrame(plow_list)

        # Beregn senterpunkt (hyttegrenda)
        center_lat = 59.392  # Midt i hyttegrenda
        center_lon = 6.4308   # Midt i hyttegrenda

        # Opprett kart
        logger.info("Oppretter basiskart")
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=16,
            tiles='CartoDB positron',
            attr='© CartoDB',
            width='100%',
            height='100%',
            prefer_canvas=True
        )

        # CSS-stil for labels
        label_style = (
            'font-size: 14px; '
            'font-weight: bold; '
            'color: {color}; '
            'text-shadow: 1px 1px 1px white, -1px -1px 1px white, '
            '1px -1px 1px white, -1px 1px 1px white;'
        )

        # Legg til markører
        logger.info("Legger til markører")
        for _, row in df.iterrows():
            color = 'blue' if row['Subscription'] == 'star_white' else 'red'
            lat = float(row['Latitude'])
            lon = float(row['Longitude'])

            # Sirkelmarkør med større touchområde
            folium.CircleMarker(
                location=[lat, lon],
                radius=12,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=2
            ).add_to(m)

            # Label med bedre touch-støtte
            folium.Marker(
                location=[lat, lon],
                icon=folium.DivIcon(
                    html=f'<div style="{label_style.format(color=color)}">'
                         f'{row["customer_id"]}</div>',
                    icon_size=(50, 30),
                    icon_anchor=(25, 0)
                )
            ).add_to(m)

        # Mobilvennlig tegnforklaring
        legend_html = """
        <div style="
            position: fixed;
            bottom: 20px;
            right: 20px;
            z-index: 1000;
            background-color: white;
            padding: 12px;
            border-radius: 8px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
            font-size: 14px;
            max-width: 80%;
        ">
            <h4 style="margin: 0 0 8px 0;">Tegnforklaring</h4>
            <div style="display: flex; align-items: center; margin: 4px 0;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: blue; margin-right: 8px;"></div>
                <span>Årsabonnement</span>
            </div>
            <div style="display: flex; align-items: center; margin: 4px 0;">
                <div style="width: 12px; height: 12px; border-radius: 50%; background: red; margin-right: 8px;"></div>
                <span>Ukentlig bestilling (*)</span>
            </div>
        </div>
        """
        m.get_root().html.add_child(folium.Element(legend_html))

        # Lagre som HTML
        html_file = DATA_DIR / f'plow_map_{target_date.strftime("%Y%m%d")}.htm'
        logger.info(f"Lagrer kart som HTML til {html_file}")

        # Legg til JavaScript for å vente på at kartet lastes
        wait_script = """
        <script>
        var mapReady = false;
        var allTilesLoaded = false;
        var lastGreyTiles = 999;
        var stableCount = 0;
        var tileLoadAttempts = {};
        var loadingStartTime = Date.now();
        
        // Forhåndslast fliser
        function preloadTile(url) {
            return new Promise((resolve, reject) => {
                var img = new Image();
                img.onload = () => resolve(url);
                img.onerror = () => reject(url);
                img.src = url;
            });
        }
        
        function checkMapRendering() {
            return new Promise((resolve) => {
                var map = document.querySelector('#map');
                var mapContainer = document.querySelector('.leaflet-container');
                var tiles = document.querySelectorAll('.leaflet-tile');
                var loadedTiles = document.querySelectorAll('.leaflet-tile-loaded');
                var visibleTiles = Array.from(tiles).filter(tile => {
                    var rect = tile.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                });
                
                // Forhåndslast nærliggende fliser
                tiles.forEach(tile => {
                    if (!tileLoadAttempts[tile.src]) {
                        tileLoadAttempts[tile.src] = 0;
                        preloadTile(tile.src).catch(() => {
                            if (tileLoadAttempts[tile.src] < 3) {
                                tileLoadAttempts[tile.src]++;
                                // Legg til timestamp og cache-buster
                                var newUrl = tile.src.split('?')[0] + 
                                    '?t=' + Date.now() + 
                                    '&cb=' + Math.random();
                                tile.src = newUrl;
                            }
                        });
                    }
                });
                
                var greyTiles = Array.from(tiles).filter(tile => {
                    var style = getComputedStyle(tile);
                    var rect = tile.getBoundingClientRect();
                    var isVisible = rect.width > 0 && rect.height > 0;
                    var isGrey = style.backgroundColor === 'rgb(128, 128, 128)';
                    var isIncomplete = !tile.complete;
                    var hasNoWidth = !tile.naturalWidth;
                    var isHidden = style.visibility === 'hidden' || style.display === 'none';
                    var isTransparent = parseFloat(style.opacity) === 0;
                    
                    // Prøv å laste på nytt med cache-busting
                    if (isVisible && (isGrey || isIncomplete || hasNoWidth)) {
                        if (tileLoadAttempts[tile.src] < 3) {
                            tileLoadAttempts[tile.src]++;
                            var newUrl = tile.src.split('?')[0] + 
                                '?t=' + Date.now() + 
                                '&cb=' + Math.random();
                            tile.src = newUrl;
                        }
                    }
                    
                    return isVisible && (isGrey || isIncomplete || hasNoWidth || isHidden || isTransparent);
                });
                
                var elapsedTime = (Date.now() - loadingStartTime) / 1000;
                console.log(`
                    ===== KARTLASTING STATUS =====
                    Tid brukt: ${elapsedTime.toFixed(1)} sekunder
                    Total antall fliser: ${tiles.length}
                    Lastede fliser: ${loadedTiles.length}
                    Synlige fliser: ${visibleTiles.length}
                    Grå/uferdige fliser: ${greyTiles.length}
                    Stabil teller: ${stableCount}
                    Forsøk gjenstår: ${maxAttempts - attempts}
                    ============================
                `);
                
                if (greyTiles.length === lastGreyTiles) {
                    stableCount++;
                } else {
                    stableCount = 0;
                }
                lastGreyTiles = greyTiles.length;
                
                var isMapReady = tiles.length > 0 && 
                                loadedTiles.length === tiles.length && 
                                visibleTiles.length > 0 &&
                                (greyTiles.length === 0 || stableCount >= 10);  // Økt til 10 sekunder
                
                if (isMapReady) {
                    allTilesLoaded = true;
                    console.log('SUKSESS: Kartet er klart for skjermbilde');
                    resolve(true);
                } else {
                    console.log('VENTER: Kartet er ikke helt klart ennå');
                    resolve(false);
                }
            });
        }
        
        function waitForMap() {
            return new Promise((resolve) => {
                var map = document.querySelector('#map');
                if (map) {
                    map.style.width = '100%';
                    map.style.height = '100vh';
                }
                
                var attempts = 0;
                var maxAttempts = 150;  // Økt til 150 sekunder
                
                var checkInterval = setInterval(async () => {
                    attempts++;
                    var isReady = await checkMapRendering();
                    
                    if (isReady) {
                        clearInterval(checkInterval);
                        console.log('Kart er ferdig rendret');
                        setTimeout(() => {
                            mapReady = true;
                            resolve();
                        }, 15000);  // Økt til 15 sekunder ekstra ventetid
                    } else if (attempts >= maxAttempts) {
                        clearInterval(checkInterval);
                        console.log('Timeout - fortsetter uansett');
                        resolve();
                    }
                }, 1000);
            });
        }

        // Start når DOM er lastet
        document.addEventListener('DOMContentLoaded', async function() {
            await waitForMap();
            console.log('READY_FOR_SCREENSHOT');
        });
        </script>
        """
        m.get_root().html.add_child(folium.Element(wait_script))
        m.save(str(html_file))

        try:
            chrome_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

            # Ta skjermbilde med Chrome
            screenshot_file = DATA_DIR / f'plow_map_{target_date.strftime("%Y%m%d")}.png'
            cmd = [
                chrome_path,
                '--headless',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--screenshot=' + str(screenshot_file),
                '--hide-scrollbars',
                '--no-sandbox',
                '--disable-web-security',
                '--wait-for-timeout=100000',
                '--disable-background-timer-throttling',
                '--run-all-compositor-stages-before-draw',
                '--force-color-profile=srgb',
                str(html_file)
            ]

            subprocess.run(cmd, check=True, capture_output=True)
            logger.info(f"Lagret skjermbilde til {screenshot_file}")

            return html_file, screenshot_file

        except Exception as e:
            logger.error(f"Feil ved generering av skjermbilde: {str(e)}")
            return html_file, None

    except Exception as e:
        logger.error(f"Feil ved oppretting av kart: {str(e)}")
        return None, None


def send_plow_plan(plow_list, map_files, target_date, config):
    """Send brøyteplan på e-post."""
    try:
        logger.info("Forbereder e-post med brøyteplan")
        if not plow_list:
            logger.warning("Ingen tun å brøyte")
            return None

        html_file, png_file = map_files

        # Opprett e-post
        msg = MIMEMultipart()
        msg['From'] = config['email_from']
        msg['To'] = config['email_to']
        subject = f"Brøyteplan for {target_date.strftime('%d.%m.%Y')}"
        msg['Subject'] = subject

        # Konverter liste til DataFrame
        df = pd.DataFrame(plow_list)

        # Funksjon for å bestemme rode
        def get_rode(customer_id):
            # Spesielle ID-er i rode 5
            if customer_id in ['3B', '3D']:
                return 5

            try:
                id_num = int(customer_id)
                if 142 <= id_num <= 168:
                    return 1
                elif 169 <= id_num <= 199:
                    return 2
                elif 214 <= id_num <= 224:
                    return 3
                elif 269 <= id_num <= 307:
                    return 4
                elif 1 <= id_num <= 13:
                    return 5
                elif 14 <= id_num <= 48:
                    return 6
                elif 51 <= id_num <= 69:
                    return 7
                return 8  # Andre
            except ValueError:
                return 8  # Andre spesielle ID-er

        # Legg til rode og sorter
        df['rode'] = df['customer_id'].apply(get_rode)
        df = df.sort_values(['rode', 'customer_id'])

        # Lag liste over tun som skal brøytes
        body = [
            f"BRØYTEPLAN FOR {target_date.strftime('%d.%m.%Y')}",
            "",
            "Oversikt over tun som skal brøytes:",
            "(* = ukentlig bestilling)"
        ]

        current_rode = None
        for _, row in df.iterrows():
            rode = row['rode']
            if rode != current_rode:
                if rode <= 7:
                    body.append(f"\nRode {rode}:")
                else:
                    body.append("\nAndre:")
                current_rode = rode

            marker = ' *' if row['Subscription'] == 'star_red' else ''
            body.append(f"- {row['customer_id']}{marker}")

        # Legg til statistikk
        total = len(df)
        yearly = len(df[df['Subscription'] == 'star_white'])
        weekly = len(df[df['Subscription'] == 'star_red'])

        body.extend([
            f"\nTotalt {total} tun",
            f"- {yearly} årsabonnement",
            f"- {weekly} ukentlige bestillinger",
            "",
            "-------------------",
            "Se vedlagte filer for kart:",
            "- HTML-fil = Interaktivt kart",
            "- PDF-fil = Utskriftsvennlig kart",
            "",
            "Blå markører = Årsabonnement",
            "Røde markører = Ukentlig bestilling"
        ])

        # Konverter body-listen til tekst
        body_text = '\n'.join(body)

        # Lagre e-postinnholdet i en fil
        email_file = DATA_DIR / f'email_content_{target_date.strftime("%Y%m%d")}.txt'
        logger.info(f"Lagrer e-postinnhold til {email_file}")
        with open(email_file, 'w') as f:
            f.write(body_text)

        msg.attach(MIMEText(body_text, 'plain'))

        # Legg ved HTML-fil
        if html_file and html_file.exists():
            logger.info("Legger ved HTML-kartfil")
            with open(html_file, encoding='utf-8') as f:
                attachment = MIMEText(f.read(), 'html')
                attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=html_file.name
                )
                msg.attach(attachment)

        # Legg ved PNG-fil
        if png_file and png_file.exists():
            logger.info("Legger ved PNG-kartfil")
            with open(png_file, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype="png")
                attachment.add_header(
                    'Content-Disposition',
                    'attachment',
                    filename=png_file.name
                )
                msg.attach(attachment)

        # Send e-post
        logger.info("Sender e-post")
        with smtplib.SMTP(config['smtp_server'], 587) as server:
            server.starttls()
            server.login(config['smtp_username'], config['smtp_password'])
            server.send_message(msg)

        logger.info("Brøyteplan sendt på e-post")

    except Exception as e:
        logger.error(f"Feil ved sending av brøyteplan: {str(e)}")
        return None


def main(target_date=None):
    """Hovedfunksjon for brøyteplanlegging."""
    try:
        logger.info("Starter brøyteplanlegging")

        # Last konfigurasjon
        config = load_config()
        if not config:
            return

        # Bruk innsendt dato eller dagens dato
        if target_date:
            target_date = pd.to_datetime(target_date)
        else:
            target_date = datetime.now()

        date_str = target_date.strftime('%d.%m.%Y')
        logger.info(f"\n=== BRØYTEPLANLEGGING FOR {date_str} ===")

        # Last kundedata
        customers_df = load_customers()
        if customers_df is None:
            return

        # Last ukentlige bestillinger
        orders_df = load_weekly_orders()
        if orders_df is None:
            return

        # Generer brøyteliste
        plow_list = get_plowing_list(customers_df, orders_df, target_date)
        if not plow_list:
            logger.info("Ingen tun skal brøytes på valgt dato")
            return

        # Lag kart (HTML og PDF)
        map_files = create_plow_map(plow_list, target_date)
        if not map_files[0] and not map_files[1]:
            return

        # Send e-post
        send_plow_plan(plow_list, map_files, target_date, config)

    except Exception as e:
        logger.error(f"Feil i hovedfunksjon: {str(e)}")
        return None


if __name__ == '__main__':
    import sys
    test_date = sys.argv[1] if len(sys.argv) > 1 else None
    main(test_date)
