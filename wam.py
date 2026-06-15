#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  WAM - WhatsApp Automate Message v5.3                                       ║
║  COM INTEGRAÇÃO REAL COM WHATSAPP WEB (Selenium)                           ║
║  Responsabilidade EXCLUSIVA do usuário - LGPD Rigorosa                      ║
║  github.com/luisfernandosiqueirasilva/whatsapp_automate_msg                ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import time
import json
import shutil
import re
import queue
import getpass
import secrets
import threading
import ctypes
import ctypes.wintypes
import csv
import zlib
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum

# ============================================================================
# VERIFICAÇÃO DO SISTEMA OPERACIONAL
# ============================================================================

def verificar_windows():
    if sys.platform != 'win32':
        print("❌ WAM requer Windows. Execute em um computador Windows.")
        sys.exit(1)

verificar_windows()

# ============================================================================
# CONSTANTES DO WINDOWS
# ============================================================================

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
KEYEVENTF_KEYUP = 0x0002

VK_CODES = {
    'esc': 0x1B,
    'enter': 0x0D,
    's': 0x53,
}

# ============================================================================
# CTYPES COM DECLARAÇÃO DE TIPOS
# ============================================================================

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.GetCursorPos.argtypes = [ctypes.POINTER(ctypes.wintypes.POINT)]
user32.GetCursorPos.restype = ctypes.c_bool

user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = ctypes.c_bool

user32.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint]
user32.mouse_event.restype = None

user32.keybd_event.argtypes = [ctypes.c_byte, ctypes.c_byte, ctypes.c_uint, ctypes.c_uint]
user32.keybd_event.restype = None

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short

user32.GetSystemMetrics.argtypes = [ctypes.c_int]
user32.GetSystemMetrics.restype = ctypes.c_int

try:
    user32.SetProcessDPIAware()
except Exception:
    pass

# ============================================================================
# PRIORIDADES
# ============================================================================

class Prioridade(Enum):
    URGENTISSIMO = 1
    URGENTE = 2
    NORMAL = 3
    BAIXA = 4
    EXPIRADO = 99


@dataclass(order=True)
class ConsultaPriorizada:
    prioridade: int
    timestamp: float = field(compare=False)
    consulta_id: str = field(compare=False)
    dados: dict = field(compare=False)
    tentativas: int = field(default=0, compare=False)


# ============================================================================
# LOGGER COM ANONIMIZAÇÃO COMPLETA
# ============================================================================

class LoggerAuditoria:
    def __init__(self, base_path: Path):
        self.pasta_logs = base_path / "logs_auditoria"
        self.pasta_logs.mkdir(parents=True, exist_ok=True)
        self.arquivo = self.pasta_logs / f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self._lock = threading.Lock()
    
    def log(self, evento: str, dados: dict = None):
        with self._lock:
            registro = {
                'timestamp': datetime.now().isoformat(),
                'evento': evento,
                'usuario': getpass.getuser(),
                'dados': self._anonimizar_completo(dados) if dados else None
            }
            with open(self.arquivo, 'a', encoding='utf-8') as f:
                f.write(json.dumps(registro, ensure_ascii=False) + '\n')
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {evento}")
    
    def _anonimizar_completo(self, dados: dict) -> dict:
        if not dados:
            return None
        anon = {}
        for key, value in dados.items():
            if isinstance(value, dict):
                anon[key] = self._anonimizar_completo(value)
            elif isinstance(value, list):
                anon[key] = [self._anonimizar_completo(v) if isinstance(v, dict) else v for v in value]
            elif isinstance(value, str):
                if 'nome' in key.lower() or 'paciente' in key.lower():
                    anon[key] = value[:2] + '***' if len(value) > 2 else '***'
                elif 'telefone' in key.lower() or 'tel' in key.lower():
                    anon[key] = '****' + value[-4:] if len(value) >= 4 else '****'
                else:
                    anon[key] = value
            else:
                anon[key] = value
        return anon


# ============================================================================
# PYAutoGUI NATIVO
# ============================================================================

class PyAutoGUINativo:
    @staticmethod
    def size():
        return (user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))
    
    @staticmethod
    def position():
        ponto = ctypes.wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(ponto))
        return (ponto.x, ponto.y)
    
    @staticmethod
    def moveTo(x, y, duration=0):
        user32.SetCursorPos(int(x), int(y))
        if duration > 0:
            time.sleep(duration)
    
    @staticmethod
    def click(x=None, y=None, button='left'):
        if x is not None and y is not None:
            PyAutoGUINativo.moveTo(x, y)
        
        if button == 'left':
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        elif button == 'right':
            user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


pyautogui = PyAutoGUINativo()

# ============================================================================
# LEITOR DE PDF
# ============================================================================

class PDFDocument:
    def __init__(self, caminho: str):
        self.caminho = caminho
        self.texto = ""
        self._carregar()
    
    def _carregar(self):
        try:
            with open(self.caminho, 'rb') as f:
                conteudo = f.read()
                
                stream_padrao = re.compile(rb'stream\s+(.*?)\s+endstream', re.DOTALL)
                streams = stream_padrao.findall(conteudo)
                
                for stream in streams:
                    try:
                        descomprimido = zlib.decompress(stream, -zlib.MAX_WBITS)
                        texto = descomprimido.decode('latin-1', errors='ignore')
                        self.texto += texto + '\n'
                    except Exception:
                        try:
                            self.texto += stream.decode('latin-1', errors='ignore') + '\n'
                        except Exception:
                            pass
                
                if not self.texto.strip():
                    texto_encontrado = re.findall(rb'\((.*?)\)', conteudo)
                    for t in texto_encontrado:
                        try:
                            parte = t.decode('latin-1', errors='ignore')
                            if re.search(r'[A-Za-zÀ-Úà-ú]', parte) and len(parte) > 3:
                                self.texto += parte + '\n'
                        except Exception:
                            pass
        except Exception as e:
            self.texto = f"Erro ao ler PDF: {e}"
    
    def extract_text(self) -> str:
        return self.texto
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        pass


class PDFPlumberNativo:
    @staticmethod
    def open(caminho):
        return PDFDocument(caminho)


pdfplumber = PDFPlumberNativo()

# ============================================================================
# CSV HELPER
# ============================================================================

class WorkbookNativo:
    def __init__(self):
        self.dados = []
    
    @property
    def active(self):
        return self
    
    def append(self, linha):
        self.dados.append(linha)
    
    @property
    def max_row(self):
        return len(self.dados)
    
    def cell(self, row, column):
        class Cell:
            def __init__(self, data, r, c):
                self._data = data
                self.r = r
                self.c = c
            
            @property
            def value(self):
                if self.r - 1 < len(self._data) and self.c - 1 < len(self._data[self.r - 1]):
                    return self._data[self.r - 1][self.c - 1]
                return None
            
            @value.setter
            def value(self, valor):
                while len(self._data) < self.r:
                    self._data.append([])
                while len(self._data[self.r - 1]) < self.c:
                    self._data[self.r - 1].append('')
                self._data[self.r - 1][self.c - 1] = valor
        
        return Cell(self.dados, row, column)
    
    def save(self, caminho):
        if not str(caminho).endswith('.csv'):
            caminho = Path(caminho).with_suffix('.csv')
        
        with open(caminho, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerows(self.dados)


def load_workbook_nativo(caminho):
    wb = WorkbookNativo()
    if str(caminho).endswith('.csv'):
        caminho_csv = caminho
    else:
        caminho_csv = Path(caminho).with_suffix('.csv')
    
    if os.path.exists(caminho_csv):
        with open(caminho_csv, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for linha in reader:
                wb.dados.append(linha)
    return wb


Workbook = WorkbookNativo
load_workbook = load_workbook_nativo

# ============================================================================
# WHATSAPP REAL COM SELENIUM
# ============================================================================

class WhatsAppReal:
    # WhatsApp Web muda o DOM com frequência; tentamos vários seletores em ordem.
    _SELETORES_CAIXA = [
        '//footer//div[@contenteditable="true"][@role="textbox"]',
        '//footer//div[@contenteditable="true"]',
        '//div[@contenteditable="true"][@data-tab="10"]',
        '//div[@contenteditable="true"][@data-tab="6"]',
    ]
    _SELETORES_LOGADO = [
        "div[aria-label='Chat list']",
        "div[data-testid='chat-list']",
        "#side",
        "div[contenteditable='true'][data-tab='3']",
    ]

    def __init__(self, logger: LoggerAuditoria, base_path: Path):
        self.logger = logger
        self.base_path = base_path
        self.driver = None
        self._lock = threading.Lock()
        self._conectado = False
    
    def conectar(self) -> bool:
        """Conecta ao WhatsApp Web"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError:
            self.logger.log("ERRO: Selenium não instalado. Execute: pip install selenium")
            return False
        
        try:
            chrome_options = Options()
            chrome_options.add_argument("--start-maximized")
            chrome_options.add_argument("--disable-notifications")
            
            # Pasta de perfil para manter login
            perfil_path = self.base_path / "whatsapp_profile"
            perfil_path.mkdir(exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={perfil_path}")
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get("https://web.whatsapp.com")
            
            print("\n📱 Escaneie o QR Code do WhatsApp Web...")
            print("Aguardando login (até 90 segundos)...")
            
            # Aguarda o login concluir (QR Code escaneado). O DOM do WhatsApp
            # Web varia, então procuramos por qualquer indicador de sessão ativa.
            def _logado(driver):
                return any(
                    driver.find_elements(By.CSS_SELECTOR, css)
                    for css in self._SELETORES_LOGADO
                )
            WebDriverWait(self.driver, 90).until(_logado)
            
            self._conectado = True
            self.logger.log("WHATSAPP_CONECTADO")
            print("✅ WhatsApp Web conectado com sucesso!")
            return True
            
        except Exception as e:
            self.logger.log(f"ERRO_CONEXAO_WHATSAPP: {str(e)[:100]}")
            return False
    
    def enviar(self, telefone: str, mensagem: str) -> bool:
        """Envia mensagem via WhatsApp Web"""
        if not self._conectado or not self.driver:
            self.logger.log("WHATSAPP_NAO_CONECTADO")
            return False
        
        if not telefone or len(telefone) < 12:
            self.logger.log(f"TELEFONE_INVALIDO: {telefone}")
            return False
        
        with self._lock:
            try:
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.common.keys import Keys
                
                url = f"https://web.whatsapp.com/send?phone={telefone}"
                self.driver.get(url)
                
                wait = WebDriverWait(self.driver, 30)
                caixa_mensagem = self._aguardar_caixa_mensagem(wait, By)
                if caixa_mensagem is None:
                    if self._numero_invalido(By):
                        self.logger.log(f"NUMERO_SEM_WHATSAPP: {telefone[:8]}***")
                    else:
                        self.logger.log(f"CAIXA_MSG_NAO_ENCONTRADA: {telefone[:8]}***")
                    return False
                
                time.sleep(1)
                
                # Digita a mensagem multi-linha sem enviar prematuramente
                # (ENTER envia no WhatsApp Web; usamos SHIFT+ENTER para quebras).
                self._digitar_mensagem(caixa_mensagem, mensagem, Keys)
                time.sleep(0.5)
                caixa_mensagem.send_keys(Keys.ENTER)
                time.sleep(2)
                
                self.logger.log("MSG_ENVIADA", {'telefone': telefone[:8] + '***'})
                return True
                
            except Exception as e:
                self.logger.log(f"ERRO_ENVIO_WHATSAPP: {str(e)[:100]}")
                return False
    
    def _aguardar_caixa_mensagem(self, wait, By):
        """Localiza a caixa de mensagem testando vários seletores em paralelo."""
        from selenium.common.exceptions import TimeoutException
        
        def _encontrar(driver):
            for xpath in self._SELETORES_CAIXA:
                for el in driver.find_elements(By.XPATH, xpath):
                    if el.is_displayed():
                        return el
            return False
        
        try:
            return wait.until(_encontrar)
        except TimeoutException:
            return None
    
    def _numero_invalido(self, By) -> bool:
        """Detecta o aviso de número sem WhatsApp exibido após o /send."""
        marcadores = [
            "phone number shared via url is invalid",
            "número de telefone compartilhado por url é inválido",
            "telefone compartilhado por meio de url é inválido",
        ]
        try:
            corpo = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            return any(m in corpo for m in marcadores)
        except Exception:
            return False
    
    def _digitar_mensagem(self, caixa, mensagem: str, Keys):
        """Digita texto multi-linha usando SHIFT+ENTER para as quebras."""
        for i, linha in enumerate(mensagem.split('\n')):
            if i > 0:
                caixa.send_keys(Keys.SHIFT, Keys.ENTER)
            if linha:
                caixa.send_keys(linha)
    
    def fechar(self):
        if self.driver:
            self.driver.quit()
            self._conectado = False


# ============================================================================
# FILA PRIORITÁRIA COM CONSUMIDOR REAL
# ============================================================================

class FilaPrioritaria:
    def __init__(self, logger: LoggerAuditoria, whatsapp: WhatsAppReal, base_path: Path):
        self.logger = logger
        self.whatsapp = whatsapp
        self.base_path = base_path
        self.fila = queue.PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.rodando = True
        self.enviados = set()
        self.falhas = {}
        # RLock (reentrante): _enviar mantém o lock e chama _salvar_historico,
        # que também adquire o mesmo lock.
        self._lock = threading.RLock()
        self._start_worker()
    
    def _start_worker(self):
        def worker():
            while self.rodando:
                try:
                    item = self.fila.get(timeout=1)
                    self.executor.submit(self._enviar, item)
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.log(f"ERRO_WORKER: {str(e)[:50]}")
        
        threading.Thread(target=worker, daemon=True).start()
    
    def _enviar(self, item: ConsultaPriorizada):
        try:
            dados = item.dados
            consulta = dados['consulta']
            medico = dados['medico']
            chave = dados['chave']
            
            # Verifica duplicata
            chave_unica = f"{consulta.get('nome', '')}_{medico}_{consulta.get('data', '')}"
            
            with self._lock:
                if chave_unica in self.enviados:
                    self.logger.log(f"DUPLICADA IGNORADA: {chave_unica}")
                    return
            
            mensagem = self._montar_mensagem(consulta, medico, chave)
            telefone = self._normalizar_telefone(consulta.get('telefone', ''))
            
            sucesso = self.whatsapp.enviar(telefone, mensagem)
            
            with self._lock:
                if sucesso:
                    self.enviados.add(chave_unica)
                    self._salvar_historico(consulta, medico, chave, sucesso)
                    status = 'OK'
                else:
                    # Registra falha para possível retry
                    self.falhas[chave_unica] = self.falhas.get(chave_unica, 0) + 1
                    if self.falhas[chave_unica] < 3:
                        # Recoloca na fila com prioridade mais baixa
                        novo_item = ConsultaPriorizada(
                            prioridade=Prioridade.BAIXA.value,
                            timestamp=time.time(),
                            consulta_id=item.consulta_id,
                            dados=item.dados,
                            tentativas=item.tentativas + 1
                        )
                        self.fila.put(novo_item)
                        status = f'RETRY {self.falhas[chave_unica]}'
                    else:
                        self._salvar_historico(consulta, medico, chave, sucesso)
                        status = 'FALHA_PERMANENTE'
            
            self.logger.log(f"ENVIO: {consulta.get('nome', '?')[:15]} | {status}")
            
        except Exception as e:
            self.logger.log(f"ERRO_ENVIO: {str(e)[:50]}")
    
    def _normalizar_telefone(self, telefone: str) -> str:
        if not telefone:
            return ""
        apenas_numeros = re.sub(r'\D', '', telefone)
        if len(apenas_numeros) < 10:
            return ""
        if len(apenas_numeros) == 10:
            return "55" + apenas_numeros
        if len(apenas_numeros) == 11:
            return "55" + apenas_numeros
        if len(apenas_numeros) == 13 and apenas_numeros.startswith('55'):
            return apenas_numeros
        return "55" + apenas_numeros[-11:] if len(apenas_numeros) > 11 else ""
    
    def _salvar_historico(self, consulta: dict, medico: str, chave: str, sucesso: bool):
        with self._lock:
            historico_path = self.base_path / "historico_envios.csv"
            arquivo_existe = historico_path.exists()
            
            with open(historico_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                if not arquivo_existe:
                    writer.writerow(['Data', 'Paciente', 'Telefone', 'Medico', 'DataConsulta', 'HoraConsulta', 'Chave', 'Status'])
                writer.writerow([
                    datetime.now().isoformat(),
                    consulta.get('nome', ''),
                    consulta.get('telefone', ''),
                    medico,
                    consulta.get('data', ''),
                    consulta.get('hora', ''),
                    chave,
                    'Enviado' if sucesso else 'Falha'
                ])
    
    def calcular_prioridade(self, data_str: str, hora_str: str) -> int:
        if not data_str:
            return Prioridade.BAIXA.value
        
        try:
            data_match = re.search(r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', data_str)
            if not data_match:
                return Prioridade.BAIXA.value
            data_limpa = data_match.group(1)
            
            data = None
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d/%m/%y']:
                try:
                    data = datetime.strptime(data_limpa, fmt)
                    break
                except ValueError:
                    continue
            
            if not data:
                return Prioridade.BAIXA.value
            
            hora = None
            if hora_str:
                hora_match = re.search(r'(\d{2}:\d{2})', hora_str)
                if hora_match:
                    hora_limpa = hora_match.group(1)
                    try:
                        hora = datetime.strptime(hora_limpa, '%H:%M').time()
                    except ValueError:
                        pass
            
            data_hora = datetime.combine(data.date(), hora) if hora else data
            horas = (data_hora - datetime.now()).total_seconds() / 3600
            
            if horas < 0:
                return Prioridade.EXPIRADO.value
            if horas < 1:
                return Prioridade.URGENTISSIMO.value
            if horas < 3:
                return Prioridade.URGENTE.value
            if horas < 6:
                return Prioridade.NORMAL.value
            return Prioridade.BAIXA.value
        except Exception:
            return Prioridade.BAIXA.value
    
    def adicionar(self, consulta: dict, medico: str, chave: str):
        prioridade = self.calcular_prioridade(consulta.get('data', ''), consulta.get('hora', ''))
        consulta_id = f"{consulta.get('nome', '')}_{medico}_{time.time()}"
        item = ConsultaPriorizada(
            prioridade=prioridade,
            timestamp=time.time(),
            consulta_id=consulta_id,
            dados={'consulta': consulta, 'medico': medico, 'chave': chave},
            tentativas=0
        )
        self.fila.put(item)
        self.logger.log(f"ENFILEIRADO: {consulta.get('nome', '?')[:15]} | Prioridade: {prioridade}")
    
    def _montar_mensagem(self, consulta: dict, medico: str, chave: str) -> str:
        return f"""Olá {consulta.get('nome', 'paciente')}!

Sua consulta com Dr(a). {medico} está agendada para {consulta.get('data', 'data a confirmar')} às {consulta.get('hora', 'horário a confirmar')}.

✅ Chave de confirmação: {chave}

Por favor, confirme sua presença.

Atenciosamente, Clínica"""
    
    def stop(self):
        self.rodando = False
        self.executor.shutdown(wait=True)


# ============================================================================
# GERENCIADOR DE PASTAS
# ============================================================================

class GerenciadorPastas:
    def __init__(self, base_path: Path, logger: LoggerAuditoria):
        self.base_path = base_path
        self.logger = logger
        self.estrutura = {}
    
    def criar_estrutura(self) -> dict:
        self.estrutura = {
            'downloads': self.base_path / 'downloads_temp',
            'planilhas': self.base_path / 'planilhas',
            'erros': self.base_path / 'erros_pdf',
            'logs': self.base_path / 'logs'
        }
        for i in range(1, 11):
            self.estrutura[f'medico{i}'] = self.base_path / f'medico_{i}'
        
        for pasta in self.estrutura.values():
            pasta.mkdir(parents=True, exist_ok=True)
        
        self.logger.log("PASTAS_CRIADAS", {k: str(v) for k, v in self.estrutura.items()})
        return {k: str(v) for k, v in self.estrutura.items()}
    
    def limpar_todos_pdfs(self) -> int:
        total = 0
        for nome, pasta in self.estrutura.items():
            if nome in ['logs', 'erros', 'planilhas']:
                continue
            if pasta.exists():
                for pdf in pasta.glob('*.pdf'):
                    try:
                        pdf.unlink()
                        total += 1
                    except Exception:
                        pass
        self.logger.log("LIMPEZA_TOTAL", {'removidos': total})
        print(f"\n🗑️ {total} PDFs removidos")
        return total
    
    def mover_para_erros(self, pdf_path: Path, motivo: str):
        destino = self.estrutura['erros'] / pdf_path.name
        shutil.move(str(pdf_path), str(destino))
        self.logger.log("PDF_MOVIDO_ERRO", {'arquivo': pdf_path.name, 'motivo': motivo})


# ============================================================================
# AUTOMAÇÃO DE DOWNLOADS (com arquivos na base_path)
# ============================================================================

class AutomacaoDownloads:
    def __init__(self, logger: LoggerAuditoria, base_path: Path):
        self.logger = logger
        self.base_path = base_path
        self.clicks = []
        self.tempo_base = 3
        self._carregar_clicks()
    
    def _carregar_clicks(self):
        clicks_path = self.base_path / 'clicks_gravados.json'
        if clicks_path.exists():
            with open(clicks_path, 'r') as f:
                self.clicks = json.load(f)
    
    def _salvar_clicks(self):
        clicks_path = self.base_path / 'clicks_gravados.json'
        with open(clicks_path, 'w') as f:
            json.dump(self.clicks, f)
    
    def gravar_cliques(self) -> bool:
        print("\n🎥 GRAVAÇÃO DE CLIQUES")
        print("Pressione 'S' para iniciar, 'ESC' para parar\n")
        input("Pressione Enter quando estiver pronto...")
        
        sequencia = []
        gravando = False
        
        def on_key(key):
            nonlocal gravando
            if key == 's':
                gravando = True
                print("▶️ GRAVANDO...")
        
        def on_click(x, y, button, pressed):
            nonlocal gravando
            if gravando and pressed:
                sequencia.append({'x': int(x), 'y': int(y)})
                print(f"   Click {len(sequencia)}: ({int(x)}, {int(y)})")
        
        listener_teclado = KeyboardListener(on_key)
        listener_mouse = MouseListener(on_click)
        
        listener_teclado.start()
        listener_mouse.start()
        
        while True:
            if user32.GetAsyncKeyState(VK_CODES.get('esc', 0x1B)) & 0x8000:
                break
            time.sleep(0.1)
        
        listener_teclado.stop()
        listener_mouse.stop()
        
        if sequencia:
            self.clicks = sequencia
            self._salvar_clicks()
            print(f"\n✅ {len(sequencia)} cliques gravados!")
            return True
        
        print("\n❌ Nenhum clique gravado!")
        return False
    
    def executar_cliques(self) -> bool:
        if not self.clicks:
            print("❌ Nenhuma sequência de cliques encontrada!")
            return False
        
        for i, click in enumerate(self.clicks, 1):
            print(f"   Click {i}/{len(self.clicks)}", end="\r")
            pyautogui.moveTo(click['x'], click['y'], duration=0.1)
            pyautogui.click()
            time.sleep(0.1)
        print(f"\n   ✅ Sequência executada")
        return True
    
    def repetir_ate_download(self, pasta_downloads: str, pasta_destino: str):
        print("\n" + "="*60)
        print("DOWNLOAD AUTOMÁTICO")
        print("="*60)
        
        # Snapshot antes do download
        pdfs_antes = set(Path(pasta_downloads).glob('*.pdf'))
        
        tentativa = 1
        tempo = self.tempo_base
        
        while tentativa <= 10:
            print(f"\n🔄 Tentativa {tentativa}/10 | Aguardando {tempo}s...")
            
            if not self.executar_cliques():
                return None
            
            time.sleep(tempo)
            
            pdfs_depois = set(Path(pasta_downloads).glob('*.pdf'))
            novos_pdfs = pdfs_depois - pdfs_antes
            
            if novos_pdfs:
                pdf = list(novos_pdfs)[0]
                destino = Path(pasta_destino) / pdf.name
                shutil.move(str(pdf), str(destino))
                print(f"\n✅ DOWNLOAD: {destino.name}")
                self.logger.log("DOWNLOAD_SUCESSO", {'arquivo': destino.name})
                return str(destino)
            
            tentativa += 1
            tempo = min(tempo * 2, 60)
            print(f"   ⚠️ Nenhum PDF novo. Nova tentativa em {tempo}s...")
        
        print("\n❌ Falha no download")
        return None


# ============================================================================
# LISTENERS SIMPLIFICADOS (apenas teclas específicas)
# ============================================================================

class KeyboardListener:
    def __init__(self, on_key=None):
        self.on_key = on_key
        self.rodando = True
    
    def start(self):
        def monitor():
            ultima_tecla = {}
            while self.rodando:
                for nome, vk in VK_CODES.items():
                    estado = user32.GetAsyncKeyState(vk) & 0x8000
                    if estado and not ultima_tecla.get(nome):
                        ultima_tecla[nome] = True
                        if self.on_key:
                            self.on_key(nome)
                        time.sleep(0.2)
                    elif not estado:
                        ultima_tecla[nome] = False
                time.sleep(0.05)
        
        threading.Thread(target=monitor, daemon=True).start()
    
    def stop(self):
        self.rodando = False


class MouseListener:
    def __init__(self, on_click=None):
        self.on_click = on_click
        self.rodando = True
    
    def start(self):
        def monitor():
            left_pressed = False
            right_pressed = False
            
            while self.rodando:
                x, y = pyautogui.position()
                
                if user32.GetAsyncKeyState(0x01) & 0x8000:
                    if not left_pressed:
                        left_pressed = True
                        if self.on_click:
                            self.on_click(x, y, 'left', True)
                else:
                    left_pressed = False
                
                if user32.GetAsyncKeyState(0x02) & 0x8000:
                    if not right_pressed:
                        right_pressed = True
                        if self.on_click:
                            self.on_click(x, y, 'right', True)
                else:
                    right_pressed = False
                
                time.sleep(0.05)
        
        threading.Thread(target=monitor, daemon=True).start()
    
    def stop(self):
        self.rodando = False


# ============================================================================
# PROCESSADOR DE PDFS (com regex melhorada)
# ============================================================================

class ProcessadorPDF:
    def __init__(self, logger: LoggerAuditoria, gerenciador_pastas: GerenciadorPastas):
        self.logger = logger
        self.gerenciador_pastas = gerenciador_pastas
    
    def extrair_com_regex(self, texto: str) -> dict:
        """Extrai dados usando regex (sem capturar newlines)"""
        dados = {
            'nome': None,
            'telefone': None,
            'data': None,
            'hora': None,
            'medicos': []
        }
        
        # Busca nome (sem \s, apenas caracteres de nome)
        nome_match = re.search(r'(?:Nome|Paciente)[:\s]+([A-Za-zÀ-Úà-ú][^\n]*)', texto, re.IGNORECASE)
        if nome_match:
            dados['nome'] = nome_match.group(1).strip()
        
        # Busca telefone
        telefone_match = re.search(r'(?:Telefone|Tel|Fone)[:\s]+([\d\(\)\s-]+)', texto, re.IGNORECASE)
        if telefone_match:
            dados['telefone'] = re.sub(r'\D', '', telefone_match.group(1))
        
        # Busca data (apenas o padrão, não a linha inteira)
        data_match = re.search(r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', texto)
        if data_match:
            dados['data'] = data_match.group(1)
        
        # Busca hora (apenas o padrão)
        hora_match = re.search(r'(\d{2}:\d{2})', texto)
        if hora_match:
            dados['hora'] = hora_match.group(1)
        
        # Busca médicos (sem \s)
        medicos_match = re.findall(r'(?:Dr|Dra|Médico)[:\s]+([A-Za-zÀ-Úà-ú][^\n]*)', texto, re.IGNORECASE)
        dados['medicos'] = [m.strip() for m in medicos_match if m.strip()]
        
        return dados
    
    def extrair_e_processar(self, pasta_medico: str, fila: FilaPrioritaria) -> int:
        pasta = Path(pasta_medico)
        if not pasta.exists():
            return 0
        
        pdfs = list(pasta.glob('*.pdf'))
        if not pdfs:
            return 0
        
        print(f"\n📄 Processando {len(pdfs)} PDF(s) de: {pasta.name}")
        
        processados = 0
        for pdf in pdfs:
            print(f"   📑 {pdf.name}")
            sucesso = False
            
            try:
                with pdfplumber.open(str(pdf)) as p:
                    texto = p.extract_text()
                    
                    # Tenta extração por regex primeiro
                    dados = self.extrair_com_regex(texto)
                    
                    # Fallback: tenta por linha se regex falhou
                    if not dados['nome'] or not dados['telefone']:
                        linhas = texto.split('\n')
                        for i, linha in enumerate(linhas):
                            if 'nome' in linha.lower() or 'paciente' in linha.lower():
                                if i + 1 < len(linhas):
                                    dados['nome'] = linhas[i + 1].strip()
                            if 'telefone' in linha.lower() or 'tel' in linha.lower():
                                if i + 1 < len(linhas):
                                    dados['telefone'] = re.sub(r'\D', '', linhas[i + 1].strip())
                            # Apenas o padrão da data/hora, não a linha toda
                            data_padrao = re.search(r'(\d{2}/\d{2}/\d{4})', linha)
                            if data_padrao:
                                dados['data'] = data_padrao.group(1)
                            hora_padrao = re.search(r'(\d{2}:\d{2})', linha)
                            if hora_padrao:
                                dados['hora'] = hora_padrao.group(1)
                    
                    if dados['nome'] and dados['telefone'] and dados['medicos']:
                        chave = ''.join(secrets.choice('0123456789') for _ in range(6))
                        for medico in dados['medicos']:
                            fila.adicionar(dados, medico, chave)
                            processados += 1
                            print(f"      ✓ {dados['nome'][:20]} → Dr. {medico}")
                        sucesso = True
                    else:
                        print(f"      ⚠️ Dados incompletos: Nome={dados['nome']}, Tel={dados['telefone']}, Médicos={len(dados['medicos'])}")
                        self.gerenciador_pastas.mover_para_erros(pdf, "Dados incompletos")
            
            except Exception as e:
                print(f"      ❌ Erro: {str(e)[:50]}")
                self.gerenciador_pastas.mover_para_erros(pdf, f"Erro: {str(e)[:50]}")
            
            # Só remove o PDF se processou com sucesso
            if sucesso:
                try:
                    pdf.unlink()
                    print(f"      🗑️ PDF removido")
                except Exception as e:
                    print(f"      ⚠️ Não foi possível remover: {e}")
        
        return processados


# ============================================================================
# SISTEMA PRINCIPAL
# ============================================================================

class WAM:
    def __init__(self):
        self.base_path = None
        self.logger = None
        self.pastas = None
        self.downloads = None
        self.processador = None
        self.fila = None
        self.whatsapp = None
        self._exibir_termo()
    
    def _exibir_termo(self):
        print("\n" + "="*80)
        print("WAM - WHATSAPP AUTOMATE MESSAGE v5.3")
        print("COM INTEGRAÇÃO REAL COM WHATSAPP WEB")
        print("RESPONSABILIDADE EXCLUSIVA DO USUÁRIO")
        print("="*80)
        print("""
⚠️  O PROGRAMADOR NÃO SE RESPONSABILIZA POR:
   • Violação da LGPD
   • Vazamento de dados
   • Uso indevido

✓ VOCÊ ASSUME TODA RESPONSABILIDADE:
   • Obter consentimento dos titulares
   • Manter dados seguros
   • Cumprir a lei
        """)
        print("="*80)
        
        confirm = input("\nDigite 'ACEITO' para continuar: ")
        if confirm != "ACEITO":
            print("❌ Cancelado")
            sys.exit(0)
    
    def menu(self):
        while True:
            print("\n" + "="*50)
            print("WAM - WHATSAPP AUTOMATE v5.3")
            print("="*50)
            print("1. CONFIGURAR PASTAS")
            print("2. GRAVAR CLIQUES")
            print("3. BAIXAR PDF (automático)")
            print("4. PROCESSAR PDFs (Médicos 1-10)")
            print("5. LIMPAR PDFs")
            print("6. CONECTAR WHATSAPP WEB")
            print("0. SAIR")
            print("="*50)
            
            opcao = input("Escolha: ").strip()
            
            if opcao == '1':
                self._configurar_sistema()
            elif opcao == '2':
                if not self.downloads:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                self.downloads.gravar_cliques()
            elif opcao == '3':
                if not self.pastas or not self.downloads:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                downloads = input("Pasta de downloads: ").strip() or str(Path.home() / "Downloads")
                destino = input("Pasta destino: ").strip() or self.pastas.estrutura.get('medico1', '')
                if destino:
                    self.downloads.repetir_ate_download(downloads, destino)
                else:
                    print("⚠️ Pasta destino inválida")
            elif opcao == '4':
                if not self.pastas or not self.fila:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                self._processar_todos_medicos()
            elif opcao == '5':
                if self.pastas:
                    self.pastas.limpar_todos_pdfs()
                else:
                    print("⚠️ Configure primeiro (opção 1)")
            elif opcao == '6':
                if not self.whatsapp:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                print("\n🔌 Conectando ao WhatsApp Web...")
                if self.whatsapp.conectar():
                    print("✅ WhatsApp Web conectado! As mensagens serão enviadas automaticamente.")
                else:
                    print("❌ Falha na conexão. Verifique se o Chrome está instalado.")
            elif opcao == '0':
                self._finalizar()
                break
            else:
                print("❌ Opção inválida!")
    
    def _configurar_sistema(self):
        print("\n" + "="*50)
        print("CONFIGURAÇÃO DO SISTEMA")
        print("="*50)
        
        base = input("Pasta base (Enter para padrão): ").strip()
        if not base:
            base = str(Path.home() / "WAM_Data")
        
        self.base_path = Path(base)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.logger = LoggerAuditoria(self.base_path)
        self.pastas = GerenciadorPastas(self.base_path, self.logger)
        self.pastas.criar_estrutura()
        
        self.downloads = AutomacaoDownloads(self.logger, self.base_path)
        self.processador = ProcessadorPDF(self.logger, self.pastas)
        
        # Inicializa WhatsApp
        self.whatsapp = WhatsAppReal(self.logger, self.base_path)
        self.fila = FilaPrioritaria(self.logger, self.whatsapp, self.base_path)
        
        print("\n✅ Sistema configurado com sucesso!")
        print("\n⚠️ Para enviar mensagens reais, execute a opção 6 para conectar ao WhatsApp Web.")
    
    def _processar_todos_medicos(self):
        print("\n" + "="*50)
        print("PROCESSANDO MÉDICOS 1-10")
        print("="*50)
        
        if not self.whatsapp._conectado:
            print("\n⚠️ WhatsApp Web não conectado!")
            conectar = input("Deseja conectar agora? (s/n): ").lower()
            if conectar == 's':
                if not self.whatsapp.conectar():
                    print("❌ Falha na conexão. Mensagens não serão enviadas.")
                    return
            else:
                print("⚠️ Mensagens serão simuladas (não enviadas)")
        
        total = 0
        for i in range(1, 11):
            pasta = self.pastas.estrutura.get(f'medico{i}')
            if pasta and pasta.exists():
                processados = self.processador.extrair_e_processar(str(pasta), self.fila)
                total += processados
        
        print(f"\n✅ {total} consultas processadas e enfileiradas")
        
        if total > 0:
            print("\n📊 Fila processando mensagens em background...")
            time.sleep(1)
    
    def _finalizar(self):
        if self.fila:
            self.fila.stop()
        if self.whatsapp:
            self.whatsapp.fechar()
        print("\nEncerrando...")


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║     WAM - WHATSAPP AUTOMATE MESSAGE v5.3                         ║
    ║     COM INTEGRAÇÃO REAL COM WHATSAPP WEB                        ║
    ║     github.com/luisfernandosiqueirasilva/whatsapp_automate_msg   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        app = WAM()
        app.menu()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()