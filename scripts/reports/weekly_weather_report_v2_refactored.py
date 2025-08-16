#!/usr/bin/env python3
"""
Ukentlig værrapport v2.1 - Refactored version using new modular structure
"""
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from snofokk.config import load_config, settings
from snofokk.models import WeatherData
from snofokk.services import analysis_service, plotting_service, weather_service

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.logs_path / 'weekly_report_v2.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def send_email_report(config, df: WeatherData, plot_file: Path) -> None:
    """Send email report (simplified for now)"""
    try:
        # Import email modules here to avoid import errors if not needed
        import smtplib
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        msg = MIMEMultipart()
        msg['From'] = config.email_from
        msg['To'] = config.email_to

        # Create subject with Norwegian date
        current_date = datetime.now(settings.tz)
        subject = f"Ukentlig værrapport for Fjellbergsskardet {current_date.strftime('%d.%m.%Y')}"
        msg['Subject'] = subject

        # Analyze period
        if 'referenceTime' in df.columns and not df.empty:
            periode_start = df['referenceTime'].min()
            periode_slutt = df['referenceTime'].max()
            periode = f"{periode_start.strftime('%d.%m')} - {periode_slutt.strftime('%d.%m.%Y')}"

            # Analyze last 24 hours
            last_24h = df[df['referenceTime'] >= (df['referenceTime'].max() - timedelta(hours=24))]

            if not last_24h.empty and 'air_temperature' in last_24h.columns:
                temp_range = (
                    f"{last_24h['air_temperature'].min():.1f}°C til "
                    f"{last_24h['air_temperature'].max():.1f}°C"
                )
            else:
                temp_range = "Ikke tilgjengelig"
        else:
            periode = "Ukjent periode"
            temp_range = "Ikke tilgjengelig"

        # Create email body
        body = f"""
Ukentlig værrapport for {periode}

SAMMENDRAG SISTE 24 TIMER:
- Temperaturspenn: {temp_range}
- Dataperiode: {periode}

Se vedlagt graf for detaljert analyse.

Hilsen
Værrapportsystemet v2.1
"""

        msg.attach(MIMEText(body, 'plain'))

        # Attach weather plot
        if plot_file.exists():
            with open(plot_file, 'rb') as f:
                img_data = f.read()
                image = MIMEImage(img_data)
                image.add_header('Content-Disposition', 'attachment', filename='weather_plot.png')
                msg.attach(image)

        # Send email
        with smtplib.SMTP(config.smtp_server, 587) as server:
            server.starttls()
            server.login(config.smtp_username, config.smtp_password)
            server.send_message(msg)

        logger.info("Weekly report sent via email")

    except Exception as e:
        logger.error(f"Error sending email report: {e}")

def main(test_mode: bool = False) -> None:
    """Main function for weekly weather report"""
    try:
        # Check if it's Friday (unless in test mode)
        if not test_mode and datetime.now().weekday() != 4:  # 4 = Friday
            logger.info("Not Friday - no report will be sent")
            return

        logger.info(f"\n=== UKENTLIG VÆRRAPPORT V2.1 STARTER {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
        if test_mode:
            logger.info(" (TEST MODE)")

        # Load configuration
        config = load_config()

        # Set up time period
        now = datetime.now(settings.tz)
        week_ago = now - timedelta(days=7)

        # Fetch weather data using new service
        logger.info("Fetching weather data...")
        df = weather_service.fetch_weather_data(
            station=config.weather_station,
            from_time=week_ago.strftime('%Y-%m-%dT%H:%M:%S'),
            to_time=now.strftime('%Y-%m-%dT%H:%M:%S'),
            client_id=config.frost_client_id
        )

        if df is None:
            logger.error("Could not fetch weather data")
            return

        logger.info(f"Fetched {len(df)} weather records")

        # Normalize snow data using new service
        df = weather_service.normalize_snow_data(df)

        # Analyze snow conditions using new service
        snow_analyses = analysis_service.analyze_snow_conditions(df)
        logger.info(f"Generated {len(snow_analyses)} snow analyses")

        # Detect risk periods
        risk_periods = analysis_service.detect_risk_periods(df)
        logger.info(f"Detected {len(risk_periods)} risk periods")

        # Create plot using new service
        plot_file = settings.data_path / 'weather_plot_v2.png'
        success, _ = plotting_service.create_weather_plot(df, snow_analyses, plot_file)

        if success:
            logger.info(f"Weather plot saved to {plot_file}")

            # Send email report
            if not test_mode:
                send_email_report(config, df, plot_file)
            else:
                logger.info("Test mode - email not sent")
        else:
            logger.error("Could not generate weather plot")

        logger.info("=== UKENTLIG VÆRRAPPORT FULLFØRT ===")

    except Exception as e:
        logger.error(f"Error in main function: {e}")
        raise

if __name__ == '__main__':
    test_mode = '--test' in sys.argv
    main(test_mode)
