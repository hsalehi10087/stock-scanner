"""تست دسترسی سرور گیت‌هاب به منابع داده‌ی بورس ایران (بدون ارسال به تلگرام)."""
import json
import os
import requests

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36',
      'Accept': 'application/json, text/plain, */*'}
TARGETS = {
    'tsetmc_codal_foolad': 'https://cdn.tsetmc.com/api/Codal/GetPreparedDataByInsCode/10/46348559193224090',
    'tsetmc_instrument_foolad': 'https://cdn.tsetmc.com/api/Instrument/GetInstrumentInfo/46348559193224090',
    'codal_excel_service': 'https://excel.codal.ir/',
    'codal_search_foolad_json': 'https://search.codal.ir/api/search/v2/q?Symbol=%D9%81%D9%88%D9%84%D8%A7%D8%AF&PageNumber=1',
    'codal_search_api': 'https://search.codal.ir/api/search/v2/q?&Audited=true&AuditorRef=-1&Category=-1&Childs=true'
                        '&CompanyState=-1&CompanyType=-1&Consolidatable=true&IsNotAudited=false&Length=-1&LetterType=-1'
                        '&Mains=true&NotAudited=true&NotConsolidatable=true&PageNumber=1&Publisher=false&TracingNo=-1&search=false',
    'tsetmc_cdn_api': 'https://cdn.tsetmc.com/api/ClosingPrice/GetMarketMap?market=0&size=1360&sector=0&typeSelected=1',
    'tsetmc_old': 'http://old.tsetmc.com/tsev2/data/MarketWatchInit.aspx?h=0&r=0',
    'rahavard': 'https://rahavard365.com/',
}
out = {}
try:
    ip = requests.get('https://ipinfo.io/json', timeout=15).json()
    out['_runner'] = {'ip_country': ip.get('country'), 'org': ip.get('org')}
except Exception as e:
    out['_runner'] = {'error': str(e)[:100]}
for k, u in TARGETS.items():
    try:
        r = requests.get(u, headers=UA, timeout=(25, 30))
        sample = r.text[:300].replace('\n', ' ')
        out[k] = {'status': r.status_code, 'len': len(r.text), 'ctype': r.headers.get('content-type', ''), 'sample': sample}
    except Exception as e:
        out[k] = {'error': str(e)[:200]}
os.makedirs('data/iran_probe', exist_ok=True)
with open('data/iran_probe/result.json', 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False, indent=1))
