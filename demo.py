import asyncio
import logging
from urllib.parse import parse_qs, urlparse

import aiohttp

from dimplex_controller import DimplexControl
from dimplex_controller.auth import AuthManager

# Configure logging
logging.basicConfig(level=logging.ERROR)


async def main():
    print("--- Dimplex Controller Demo ---")

    async with aiohttp.ClientSession() as session:
        auth = AuthManager(session)

        # Check if we already have tokens
        existing_tokens = AuthManager.load_tokens("dimplex_tokens.json")
        if existing_tokens:
            print("Found existing tokens in 'dimplex_tokens.json'. Using them...")
            auth = AuthManager(session, existing_tokens)
        else:
            # 1. Login Flow
            login_url = auth.get_login_url()
            print(f"\n1. Please visit this URL to login:\n\n{login_url}\n")
            print("IMPORTANT: Since we are impersonating the mobile app, the final redirect will fail.")
            print("To capture the code:")
            print("1. Open Developer Tools (F12) in your browser BEFORE logging in.")
            print("2. Go to the 'Network' tab and ensure 'Preserve log' is checked.")
            print("3. complete the login flow.")
            print("4. Look for a cancelled/failed request starting with 'msal...' or the value in Redirect URI.")
            print("5. Copy that full URL (or just the 'code' parameter) and paste it below.")

            # 2. Get Code
            user_input = input("\nPaste the full Redirect URL (or just the code): ").strip()

            code = ""
            if "code=" in user_input:
                try:
                    parsed = urlparse(user_input)
                    query = parse_qs(parsed.query)
                    code = query.get("code", [""])[0]
                except ValueError:
                    import re

                    match = re.search(r"code=([^&]+)", user_input)
                    if match:
                        code = match.group(1)
            else:
                code = user_input

            if not code:
                print("Error: Could not find 'code' in the input.")
                return

            print(f"\nToken exchange code found: {code[:10]}...")

            # 3. Exchange Code
            try:
                await auth.exchange_code(code)
                print("Authentication successful!")
                auth.save_tokens("dimplex_tokens.json")
            except Exception as e:
                print(f"Authentication failed: {e}")
                return

        # 4. Initialize Client
        # We pass the auth manager's tokens to the client
        client = DimplexControl(session)
        # Verify access token (refresh if needed)
        try:
            await auth.get_access_token()
        except Exception as e:
            print(f"Failed to refresh/get token: {e}")
            return

        # Re-inject verified tokens into client (or client could share auth manager, but currently separated)
        client.auth._access_token = auth._access_token
        client.auth._refresh_token = auth._refresh_token
        client.auth._expires_at = auth._expires_at

        print("\n--- API Data ---")

        # 5. User Context
        try:
            user = await client.get_user_context()
            print(f"Logged in as: {user.Name} ({user.EmailAddress})")
        except Exception as e:
            print(f"Error fetching user context: {e}")

        # 6. Fetch Hubs and Appliances
        try:
            hubs = await client.get_hubs()
            print(f"Found {len(hubs)} Hubs:")

            for hub in hubs:
                hub_name = hub.Name if hub.Name else hub.FriendlyName or "Unknown Hub"
                print(f"\n[Hub] {hub_name} (ID: {hub.HubId})")

                zones = await client.get_hub_zones(hub.HubId)
                print(f"  Found {len(zones)} Zones:")

                appliance_ids = []
                for zone in zones:
                    print(f"    - {zone.ZoneName} ({zone.ZoneType})")
                    for appliance in zone.Appliances:
                        appliance_str = (
                            f"      * {appliance.ApplianceModel} - "
                            f"{appliance.FriendlyName} (ID: {appliance.ApplianceId})"
                        )
                        print(appliance_str)
                        appliance_ids.append(appliance.ApplianceId)

                        try:
                            # Features includes schedule/mode
                            details = await client.get_appliance_features(hub.HubId, appliance.ApplianceId)
                            print(f"        Mode: {details.TimerMode} | " f"Periods: {len(details.TimerPeriods)}")
                        except Exception as e:
                            print(f"        (Could not fetch details: {e})")

                # Fetch real-time overview for all appliances in this hub
                if appliance_ids:
                    print("\n  --- Real-time Overview ---")
                    try:
                        overview = await client.get_appliance_overview(hub.HubId, appliance_ids)
                        for status in overview:
                            print(f"    * {status.ApplianceId}:")
                            print(
                                f"      - Temp: {status.RoomTemperature}°C | "
                                f"Target: {status.ActiveSetPointTemperature}°C"
                            )
                            print(f"      - Comfort: {'Yes' if status.ComfortStatus else 'No'}")
                            eco_status = "Enabled" if status.EcoStartEnabled else "Disabled"
                            print(f"      - EcoStart: {eco_status}")
                            if status.BoostDuration:
                                print(
                                    f"      - BOOST ACTIVE: {status.BoostTemperature}°C for {status.BoostDuration} mins"
                                )

                        # Example of toggling a setting (Commented out to be safe!)
                        # print("\n  Example: Toggling EcoStart for the first appliance...")
                        # await client.set_eco_start(hub.HubId, [appliance_ids[0]], True)

                        # Example of Boost (ApplianceMode 16)
                        # from dimplex_controller.models import ApplianceModeSettings
                        # boost = ApplianceModeSettings(ApplianceModes=16, Status=1, Temperature=25.0)
                        # await client.set_appliance_mode(hub.HubId, [appliance_ids[0]], boost)

                    except Exception as e:
                        print(f"    (Could not fetch or interact with overview: {e})")

        except Exception as e:
            print(f"Error fetching data: {e}")


if __name__ == "__main__":
    asyncio.run(main())
