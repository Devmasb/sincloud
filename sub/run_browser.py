import asyncio
import sub.common as common
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from sub.handle_message import handle_message
from playwright._impl._errors import TargetClosedError

# Importar el solver
from sub.solver import CloudflareSolver, ChallengeType

COOKIE_DIR = './cookies/'

async def run_browser_script(user_input):
    # Primero resolver Cloudflare antes de abrir el navegador principal
    solver = CloudflareSolver(
        challenge_type=ChallengeType.CHALLENGE,  # o TURNSTILE si aplica
        headless=True,
        os=["windows"],
        debug=True,
        retries=30
    )
    result = await solver.solve("https://qxbroker.com/en/trade")

    if not result:
        raise Exception("? No se pudo resolver Cloudflare challenge")

    print(f"? Cloudflare resuelto: {result.name}={result.value}")

    async with async_playwright() as p:
        print("Browser is opening...")
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-infobars',
                '--disable-extensions',
                '--disable-dev-shm-usage',
                '--disable-setuid-sandbox',
                '--disable-blink-features=AutomationControlled'
            ]
        )

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1366, 'height': 768}
        )

        trade_page = await context.new_page()

        url = {'live': 'https://qxbroker.com/en/trade',
               'demo': 'https://qxbroker.com/en/demo-trade'}[user_input['account_type']]
        urlcookie1 = 'https://qxbroker.com/'
        urlcookie2 = 'https://ws2.qxbroker.com/'

        # Inyectar la cookie cf_clearance obtenida por el solver
        await context.add_cookies([{
            "name": result.name,
            "value": result.value,
            "domain": result.domain,
            "path": result.path,
            "expires": result.expires,
            "httpOnly": result.http_only,
            "secure": result.secure,
            "sameSite": result.same_site
        }])

        # Funci para borrar cookies especficas
        async def delete_specific_cookie(context, cookie_name):
            try:
                cookies = await context.cookies()
                for cookie in cookies:
                    if cookie.get('name') == cookie_name:
                        await context.clear_cookies(
                            name=cookie_name,
                            domain=cookie['domain'],
                            path=cookie['path']
                        )
                        return
            except TargetClosedError:
                print("Context or page is closed, cannot delete cookie.")
            except Exception as e:
                print(f"Error deleting cookie: {e}")

        # Función para borrar cookies periódicamente
        async def periodic_cookie_deletion(context, cookie_name, interval):
            while True:
                try:
                    await delete_specific_cookie(context, cookie_name)
                except TargetClosedError:
                    print("Context or page is closed, exiting the loop.")
                    break
                except Exception as e:
                    print(f"Exception during periodic deletion: {e}")
                    break
                await asyncio.sleep(interval)

        try:
            # Exponer función para mensajes WebSocket
            await trade_page.expose_function(
                'notifyBackend',
                lambda event, message: handle_message(trade_page, event, message)
            )

            # Inyectar cookies guardadas en archivos locales
            await trade_page.context.add_cookies(
                build_cookie(
                    loads_cookie(common.file_get_contents(f"{COOKIE_DIR}{common.gstrb('//', '/', url)}.txt")),
                    urlcookie1
                )
            )
            await trade_page.context.add_cookies(
                build_cookie(
                    loads_cookie(common.file_get_contents(f"{COOKIE_DIR}{common.gstrb('//', '/', url)}.txt")),
                    urlcookie2
                )
            )

            # Inyectar scripts antes de que cargue la página
            await trade_page.add_init_script(
                common.file_get_contents('bypass.js') + common.file_get_contents('wsHook.js')
            )

            # Abrir la página de trading
            await trade_page.goto(url, timeout=60000)
            print("? Pagina cargada con cookie valida")

            # Iniciar borrado periódico de cf_clearance
            cookie_task = asyncio.create_task(periodic_cookie_deletion(trade_page.context, 'cf_clearance', 5))

            # Esperar carga completa
            await trade_page.wait_for_load_state('load')
            print("Browser loaded.")

            # Esperar cierre de la página
            await trade_page.wait_for_event('close', timeout=0)
            cookie_task.cancel()

        except TargetClosedError:
            print("Context or page is closed, exiting")
        except Exception as e:
            print(f"Exception durante ejecución: {e}")
        finally:
            pass

def build_cookie(cookies, url, expiration_time=86400):
    expiration_date = (datetime.now() + timedelta(seconds=expiration_time)).timestamp()
    return [
        {'name': name, 'value': value, 'url': url, 'expires': expiration_date}
        for name, value in cookies.items()
    ]

def loads_cookie(content, join=False):
    cookies = {
        line.split('\t')[5]: line.split('\t')[6]
        for line in content.splitlines()
        if line.strip() and not (line.startswith('#') and not line.startswith('#HttpOnly'))
    }
    return '&'.join([f'{key}={value}' for key, value in cookies.items()]) if join else cookies