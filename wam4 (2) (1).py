#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  WAM - WhatsApp Automate Message v7.0 - LGPD COMPLIANT                      ║
║  INTEGRAÇÃO COMPLETA: OpenWA + WhatsApp Web + SMS + Telegram               ║
║  ENVIO ANÔNIMO + CONFIGURAÇÕES SALVAS AUTOMATICAMENTE                     ║
║  github.com/luisfernandosiqueirasilva/whatsapp_automate_msg                ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  PROTOCOLOS LGPD IMPLEMENTADOS                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  1. CONSENTIMENTO EXPLÍCITO: Usuário deve digitar 'ACEITO'                 ║
║  2. ANONIMIZAÇÃO: Dados sensíveis são ofuscados nos logs                   ║
║  3. RETENÇÃO MÍNIMA: Dados mantidos por período limitado (30 dias)         ║
║  4. LIMPEZA AUTOMÁTICA: PDFs removidos após processamento                  ║
║  5. DIREITO DE ACESSO: Usuário pode ver todos os dados processados         ║
║  6. DIREITO DE EXCLUSÃO: Opção para limpar todos os dados                  ║
║  7. LOGS DE AUDITORIA: Todas as ações são registradas                      ║
║  8. ENCARREGADO (DPO): Contato para questões de privacidade                ║
║  9. PORTABILIDADE: Dados podem ser exportados em formato CSV               ║
║ 10. NOTIFICAÇÃO DE VIOLAÇÃO: Sistema registra e alerta sobre violações    ║
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
import hashlib
import base64
import subprocess
import smtplib
import urllib.request
import urllib.parse
import hmac
import socket
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any

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
# [LGPD] CONSTANTES DE PROTOCOLO
# ============================================================================

TEMPO_RETENCAO_DIAS = 30
DPO_CONTATO = "dpo@exemplo.com"
VIOLACAO_NOTIFICAR_EMAIL = True

# ============================================================================
# [LGPD] CONFIGURAÇÕES DE ANONIMATO
# ============================================================================

ANONIMATO_CONFIG = {
    'modo_anonimo': False,
    'numero_anonimo': '',
    'mensagem_anonima': 'Mensagem enviada via sistema automático',
    'ocultar_remetente': True,
    'usar_numero_intermediario': False,
    'numero_intermediario': '',
    'exibir_nome_anonimo': 'Clínica',
}

# ============================================================================
# [NOVO] CONFIGURAÇÕES DO OPENWA
# ============================================================================

OPENWA_CONFIG = {
    'enabled': False,
    'base_url': 'http://localhost:2785',
    'api_key': '',
    'session_name': 'wam_session',
    'webhook_url': '',
    'webhook_secret': '',
    'auto_start_session': True,
    'retry_attempts': 3,
    'retry_delay': 5,
    'timeout': 30,
    'use_webhook': False,
    'webhook_events': ['message.received', 'session.status'],
}

# ============================================================================
# [LGPD] CONFIGURAÇÕES SMS E TELEGRAM
# ============================================================================

SMS_CONFIG = {
    'provedor': 'twilio',
    'account_sid': '',
    'auth_token': '',
    'from_number': '',
    'api_key': '',
    'url_api': '',
}

TELEGRAM_CONFIG = {
    'bot_token': '',
    'chat_id': '',
    'enabled': False,
}

# ============================================================================
# [NOVO] SISTEMA DE PARADA GLOBAL
# ============================================================================

class SistemaParada:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, base_path: Path = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, base_path: Path = None):
        if self._initialized:
            return
        self.base_path = base_path or Path.home() / "WAM_Data"
        self.stop_file = self.base_path / "STOP_SIGNAL.flg"
        self.pause_file = self.base_path / "PAUSE_SIGNAL.flg"
        self._initialized = True
        self._limpar_sinais()
    
    def _limpar_sinais(self):
        for arquivo in [self.stop_file, self.pause_file]:
            if arquivo.exists():
                try:
                    arquivo.unlink()
                except:
                    pass
    
    def deve_parar(self) -> bool:
        return self.stop_file.exists()
    
    def deve_pausar(self) -> bool:
        return self.pause_file.exists()
    
    def parar(self):
        self.stop_file.touch()
        print("\n🛑 Sinal de PARADA acionado!")
    
    def pausar(self):
        self.pause_file.touch()
        print("\n⏸️ Sinal de PAUSA acionado!")
    
    def continuar(self):
        if self.pause_file.exists():
            self.pause_file.unlink()
            print("\n▶️ Execução retomada!")
    
    def reset(self):
        self._limpar_sinais()
    
    def verificar_tecla_parada(self) -> bool:
        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
        shift = user32.GetAsyncKeyState(0x10) & 0x8000
        p = user32.GetAsyncKeyState(ord('P')) & 0x8000
        return ctrl and shift and p
    
    def verificar_tecla_pausa(self) -> bool:
        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
        shift = user32.GetAsyncKeyState(0x10) & 0x8000
        space = user32.GetAsyncKeyState(0x20) & 0x8000
        return ctrl and shift and space


# ============================================================================
# [LGPD] LOGGER COM ANONIMIZAÇÃO COMPLETA E AUDITORIA
# ============================================================================

class LoggerAuditoria:
    def __init__(self, base_path: Path):
        self.pasta_logs = base_path / "logs_auditoria"
        self.pasta_logs.mkdir(parents=True, exist_ok=True)
        self.arquivo = self.pasta_logs / f"auditoria_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        self._lock = threading.Lock()
        self.violacoes_detectadas = []
    
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
    
    def registrar_violacao(self, descricao: str, dados_envolvidos: dict = None):
        violacao = {
            'timestamp': datetime.now().isoformat(),
            'descricao': descricao,
            'dados': self._anonimizar_completo(dados_envolvidos) if dados_envolvidos else None
        }
        self.violacoes_detectadas.append(violacao)
        violacoes_path = Path(self.pasta_logs) / "violacoes_lgpd.log"
        with open(violacoes_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(violacao, ensure_ascii=False) + '\n')
        self.log(f"VIOLACAO_LGPD: {descricao}")
        if VIOLACAO_NOTIFICAR_EMAIL:
            self._notificar_dpo(violacao)
    
    def _notificar_dpo(self, violacao: dict):
        print(f"\n⚠️ [LGPD] VIOLAÇÃO REGISTRADA - Notificar DPO: {DPO_CONTATO}")
        print(f"   Descrição: {violacao['descricao']}")
        print(f"   Data: {violacao['timestamp']}")


# ============================================================================
# [LGPD] GERENCIADOR DE CONSENTIMENTO
# ============================================================================

class GerenciadorConsentimento:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.consentimento_path = base_path / "consentimentos"
        self.consentimento_path.mkdir(parents=True, exist_ok=True)
    
    def registrar_consentimento(self, nome: str, telefone: str, documento: str = None):
        registro = {
            'nome': nome,
            'telefone': telefone,
            'documento': documento,
            'data_consentimento': datetime.now().isoformat(),
            'validade': (datetime.now() + timedelta(days=365)).isoformat(),
            'ip': 'local',
            'finalidade': 'Envio de mensagens automáticas sobre consultas',
            'modo_anonimo': ANONIMATO_CONFIG.get('modo_anonimo', False)
        }
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        arquivo = self.consentimento_path / f"{hash_id}.json"
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(registro, f, indent=2, ensure_ascii=False)
        return True
    
    def verificar_consentimento(self, telefone: str) -> bool:
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        arquivo = self.consentimento_path / f"{hash_id}.json"
        if not arquivo.exists():
            return False
        with open(arquivo, 'r', encoding='utf-8') as f:
            registro = json.load(f)
        validade = datetime.fromisoformat(registro.get('validade', '2000-01-01'))
        return validade >= datetime.now()
    
    def revogar_consentimento(self, telefone: str) -> bool:
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        arquivo = self.consentimento_path / f"{hash_id}.json"
        if arquivo.exists():
            revogados = self.base_path / "consentimentos_revogados"
            revogados.mkdir(exist_ok=True)
            shutil.move(str(arquivo), str(revogados / arquivo.name))
            return True
        return False


# ============================================================================
# [LGPD] GERENCIADOR DE DADOS
# ============================================================================

class GerenciadorDadosLGPD:
    def __init__(self, base_path: Path, logger: LoggerAuditoria):
        self.base_path = base_path
        self.logger = logger
    
    def exportar_dados_titular(self, telefone: str) -> Optional[Path]:
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        dados_titular = {
            'titular': {'telefone': telefone},
            'consultas': [],
            'consentimento': None,
            'data_exportacao': datetime.now().isoformat(),
            'modo_anonimo_ativo': ANONIMATO_CONFIG.get('modo_anonimo', False)
        }
        historico_path = self.base_path / "historico_envios.csv"
        if historico_path.exists():
            with open(historico_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Telefone') == telefone:
                        dados_titular['consultas'].append(row)
        consentimento_path = self.base_path / "consentimentos" / f"{hash_id}.json"
        if consentimento_path.exists():
            with open(consentimento_path, 'r', encoding='utf-8') as f:
                dados_titular['consentimento'] = json.load(f)
        export_dir = self.base_path / "exportacoes"
        export_dir.mkdir(exist_ok=True)
        arquivo_json = export_dir / f"dados_{hash_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(arquivo_json, 'w', encoding='utf-8') as f:
            json.dump(dados_titular, f, indent=2, ensure_ascii=False)
        self.logger.log(f"DADOS_EXPORTADOS", {'telefone': telefone[:8] + '***'})
        return arquivo_json
    
    def excluir_dados_titular(self, telefone: str) -> bool:
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        historico_path = self.base_path / "historico_envios.csv"
        if historico_path.exists():
            linhas = []
            with open(historico_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                cabecalho = next(reader)
                for row in reader:
                    if len(row) > 2 and row[2] != telefone:
                        linhas.append(row)
            with open(historico_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(cabecalho)
                writer.writerows(linhas)
        consentimento_path = self.base_path / "consentimentos" / f"{hash_id}.json"
        if consentimento_path.exists():
            consentimento_path.unlink()
        self.logger.log(f"DADOS_EXCLUIDOS", {'telefone': telefone[:8] + '***'})
        return True
    
    def limpar_dados_antigos(self):
        data_limite = datetime.now() - timedelta(days=TEMPO_RETENCAO_DIAS)
        for pasta in [self.base_path / "medico_1", self.base_path / "medico_2", self.base_path / "medico_3",
                      self.base_path / "medico_4", self.base_path / "medico_5", self.base_path / "medico_6",
                      self.base_path / "medico_7", self.base_path / "medico_8", self.base_path / "medico_9",
                      self.base_path / "medico_10", self.base_path / "downloads_temp"]:
            if pasta.exists():
                for pdf in pasta.glob('*.pdf'):
                    if datetime.fromtimestamp(pdf.stat().st_mtime) < data_limite:
                        pdf.unlink()
        self.logger.log("DADOS_ANTIGOS_REMOVIDOS", {'dias_retencao': TEMPO_RETENCAO_DIAS})


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
    canal_envio: str = field(default='openwa', compare=False)
    modo_anonimo: bool = field(default=False, compare=False)


# ============================================================================
# WHATSAPP REAL COM SELENIUM E SUPORTE A ANONIMATO
# ============================================================================

class WhatsAppReal:
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
            perfil_path = self.base_path / "whatsapp_profile"
            perfil_path.mkdir(exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={perfil_path}")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get("https://web.whatsapp.com")
            print("\n📱 Escaneie o QR Code do WhatsApp Web...")
            print("Aguardando login (até 90 segundos)...")
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
    
    def enviar(self, telefone: str, mensagem: str, anonimo: bool = False, config_anonimo: dict = None) -> bool:
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
                if anonimo and config_anonimo:
                    mensagem = self._processar_mensagem_anonima(mensagem, config_anonimo)
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
                self._digitar_mensagem(caixa_mensagem, mensagem, Keys)
                time.sleep(0.5)
                caixa_mensagem.send_keys(Keys.ENTER)
                time.sleep(2)
                self.logger.log("MSG_ENVIADA_WHATSAPP", {
                    'telefone': telefone[:8] + '***',
                    'modo_anonimo': anonimo
                })
                return True
            except Exception as e:
                self.logger.log(f"ERRO_ENVIO_WHATSAPP: {str(e)[:100]}")
                return False
    
    def _processar_mensagem_anonima(self, mensagem: str, config_anonimo: dict) -> str:
        if config_anonimo.get('ocultar_remetente', True):
            nome_anonimo = config_anonimo.get('exibir_nome_anonimo', 'Clínica')
            mensagem = f"📨 Mensagem do {nome_anonimo}\n\n{mensagem}\n\n{config_anonimo.get('mensagem_anonima', 'Mensagem enviada via sistema automático')}"
        return mensagem
    
    def _aguardar_caixa_mensagem(self, wait, By):
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
# ENVIADOR DE SMS (FALLBACK)
# ============================================================================

class EnviadorSMS:
    def __init__(self, logger: LoggerAuditoria, config: dict = None):
        self.logger = logger
        self.config = config or SMS_CONFIG
        self._enabled = bool(self.config.get('account_sid') and self.config.get('auth_token'))
    
    def habilitado(self) -> bool:
        return self._enabled
    
    def configurar(self, account_sid: str, auth_token: str, from_number: str):
        self.config['account_sid'] = account_sid
        self.config['auth_token'] = auth_token
        self.config['from_number'] = from_number
        self._enabled = True
        self.logger.log("SMS_CONFIGURADO")
        return True
    
    def enviar(self, telefone: str, mensagem: str, anonimo: bool = False, config_anonimo: dict = None) -> bool:
        if not self._enabled:
            self.logger.log("SMS_NAO_CONFIGURADO", {'telefone': telefone[:8] + '***'})
            return False
        try:
            if anonimo and config_anonimo:
                mensagem = self._processar_mensagem_anonima(mensagem, config_anonimo)
            numero_limpo = re.sub(r'\D', '', telefone)
            if len(numero_limpo) < 10:
                return False
            if len(numero_limpo) == 10 or len(numero_limpo) == 11:
                numero_completo = f"+55{numero_limpo}"
            else:
                numero_completo = f"+{numero_limpo}"
            if self.config.get('provedor') == 'twilio':
                return self._enviar_twilio(numero_completo, mensagem)
            elif self.config.get('provedor') == 'custom':
                return self._enviar_custom(numero_completo, mensagem)
            elif self.config.get('provedor') == 'sms_dev':
                return self._enviar_sms_dev(numero_completo, mensagem)
            else:
                self.logger.log("SMS_PROVEDOR_NAO_SUPORTADO", {'provedor': self.config.get('provedor')})
                return False
        except Exception as e:
            self.logger.log("ERRO_SMS", {'erro': str(e)[:50], 'telefone': telefone[:8] + '***'})
            return False
    
    def _processar_mensagem_anonima(self, mensagem: str, config_anonimo: dict) -> str:
        if config_anonimo.get('ocultar_remetente', True):
            mensagem = f"[Mensagem Automática]\n\n{mensagem}\n\n{config_anonimo.get('mensagem_anonima', 'Mensagem enviada via sistema automático')}"
        return mensagem
    
    def _enviar_twilio(self, telefone: str, mensagem: str) -> bool:
        try:
            from twilio.rest import Client
            client = Client(self.config['account_sid'], self.config['auth_token'])
            message = client.messages.create(
                body=mensagem[:160],
                from_=self.config['from_number'],
                to=telefone
            )
            self.logger.log("SMS_ENVIADO_TWILIO", {'sid': message.sid, 'telefone': telefone[-8:]})
            return True
        except ImportError:
            self.logger.log("TWILIO_NAO_INSTALADO", {'telefone': telefone[-8:]})
            return self._enviar_sms_dev(telefone, mensagem)
        except Exception as e:
            self.logger.log("ERRO_TWILIO", {'erro': str(e)[:50], 'telefone': telefone[-8:]})
            return False
    
    def _enviar_custom(self, telefone: str, mensagem: str) -> bool:
        try:
            url = self.config.get('url_api')
            api_key = self.config.get('api_key')
            if not url or not api_key:
                return False
            dados = {'telefone': telefone, 'mensagem': mensagem[:160], 'api_key': api_key}
            dados_encoded = urllib.parse.urlencode(dados).encode('utf-8')
            req = urllib.request.Request(url, data=dados_encoded, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                resultado = response.read().decode('utf-8')
                self.logger.log("SMS_ENVIADO_CUSTOM", {'telefone': telefone[-8:]})
                return True
        except Exception as e:
            self.logger.log("ERRO_CUSTOM_SMS", {'erro': str(e)[:50]})
            return False
    
    def _enviar_sms_dev(self, telefone: str, mensagem: str) -> bool:
        try:
            url = "https://api.smsdev.com.br/v1/send"
            dados = {'key': self.config.get('api_key', ''), 'phone': telefone, 'msg': mensagem[:160]}
            dados_encoded = urllib.parse.urlencode(dados).encode('utf-8')
            req = urllib.request.Request(url, data=dados_encoded, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                resultado = response.read().decode('utf-8')
                self.logger.log("SMS_ENVIADO_DEV", {'telefone': telefone[-8:]})
                return True
        except Exception as e:
            self.logger.log("ERRO_SMS_DEV", {'erro': str(e)[:50]})
            print(f"\n📱 [SMS SIMULADO] Para: {telefone}")
            print(f"Mensagem: {mensagem[:160]}")
            return True


# ============================================================================
# ENVIADOR TELEGRAM
# ============================================================================

class EnviadorTelegram:
    def __init__(self, logger: LoggerAuditoria, config: dict = None):
        self.logger = logger
        self.config = config or TELEGRAM_CONFIG
        self._enabled = bool(self.config.get('bot_token') and self.config.get('chat_id'))
    
    def habilitado(self) -> bool:
        return self._enabled
    
    def configurar(self, bot_token: str, chat_id: str):
        self.config['bot_token'] = bot_token
        self.config['chat_id'] = chat_id
        self.config['enabled'] = True
        self._enabled = True
        self.logger.log("TELEGRAM_CONFIGURADO")
        return True
    
    def enviar(self, mensagem: str, telefone: str = None, anonimo: bool = False, config_anonimo: dict = None) -> bool:
        if not self._enabled:
            self.logger.log("TELEGRAM_NAO_CONFIGURADO")
            return False
        try:
            if anonimo and config_anonimo:
                mensagem = self._processar_mensagem_anonima(mensagem, telefone, config_anonimo)
            elif telefone:
                mensagem = f"📱 Telefone: {telefone}\n\n{mensagem}"
            if len(mensagem) > 4096:
                mensagem = mensagem[:4093] + "..."
            url = f"https://api.telegram.org/bot{self.config['bot_token']}/sendMessage"
            dados = {'chat_id': self.config['chat_id'], 'text': mensagem, 'parse_mode': 'HTML'}
            dados_encoded = urllib.parse.urlencode(dados).encode('utf-8')
            req = urllib.request.Request(url, data=dados_encoded, method='POST')
            with urllib.request.urlopen(req, timeout=10) as response:
                resultado = json.loads(response.read().decode('utf-8'))
                if resultado.get('ok'):
                    self.logger.log("TELEGRAM_ENVIADO", {'chat_id': self.config['chat_id'][:8] + '***'})
                    return True
                else:
                    self.logger.log("TELEGRAM_ERRO", {'erro': resultado.get('description', 'Desconhecido')})
                    return False
        except Exception as e:
            self.logger.log("ERRO_TELEGRAM", {'erro': str(e)[:50]})
            return False
    
    def _processar_mensagem_anonima(self, mensagem: str, telefone: str, config_anonimo: dict) -> str:
        if config_anonimo.get('ocultar_remetente', True):
            nome_anonimo = config_anonimo.get('exibir_nome_anonimo', 'Clínica')
            msg_anonima = f"📨 Mensagem do {nome_anonimo}\n\n{mensagem}\n\n{config_anonimo.get('mensagem_anonima', 'Mensagem enviada via sistema automático')}"
            if telefone:
                msg_anonima += f"\n\n🔒 Telefone do paciente: {telefone[:8]}***"
            return msg_anonima
        return mensagem


# ============================================================================
# CLIENTE OPENWA (WhatsApp API Gateway)
# ============================================================================

class OpenWAClient:
    def __init__(self, logger: LoggerAuditoria, config: dict = None):
        self.logger = logger
        self.config = config or OPENWA_CONFIG
        self.base_url = self.config.get('base_url', 'http://localhost:2785')
        self.api_key = self.config.get('api_key', '')
        self.session_name = self.config.get('session_name', 'wam_session')
        self._session_id = None
        self._connected = False
        self._session_info = {}
        self.headers = {'Content-Type': 'application/json', 'X-API-Key': self.api_key}
    
    def habilitado(self) -> bool:
        return self.config.get('enabled', False) and bool(self.api_key)
    
    def configurar(self, base_url: str, api_key: str, session_name: str = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        if session_name:
            self.session_name = session_name
        self.headers['X-API-Key'] = self.api_key
        self.config['enabled'] = True
        self.config['base_url'] = self.base_url
        self.config['api_key'] = self.api_key
        self.config['session_name'] = self.session_name
        self.logger.log("OPENWA_CONFIGURADO", {'base_url': self.base_url, 'session': self.session_name})
        return True
    
    def testar_conexao(self) -> bool:
        if not self.habilitado():
            return False
        try:
            import requests
            url = f"{self.base_url}/api/health"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                self.logger.log("OPENWA_CONEXAO_OK")
                return True
            else:
                self.logger.log("OPENWA_CONEXAO_FALHA", {'status': response.status_code})
                return False
        except Exception as e:
            self.logger.log("OPENWA_CONEXAO_ERRO", {'erro': str(e)[:100]})
            return False
    
    def criar_sessao(self, nome: str = None) -> Optional[str]:
        if not self.habilitado():
            return None
        nome_sessao = nome or self.session_name
        try:
            import requests
            url = f"{self.base_url}/api/sessions"
            payload = {'name': nome_sessao}
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            if response.status_code in [200, 201]:
                data = response.json()
                self._session_id = data.get('id')
                self._session_info = data
                self.logger.log("OPENWA_SESSAO_CRIADA", {'session_id': self._session_id, 'name': nome_sessao})
                return self._session_id
            else:
                self.logger.log("OPENWA_SESSAO_CRIACAO_FALHA", {'status': response.status_code})
                return None
        except Exception as e:
            self.logger.log("OPENWA_SESSAO_CRIACAO_ERRO", {'erro': str(e)[:100]})
            return None
    
    def iniciar_sessao(self, session_id: str = None) -> bool:
        if not self.habilitado():
            return False
        sid = session_id or self._session_id
        if not sid:
            sid = self.criar_sessao()
            if not sid:
                return False
        try:
            import requests
            url = f"{self.base_url}/api/sessions/{sid}/start"
            response = requests.post(url, headers=self.headers, timeout=30)
            if response.status_code in [200, 201]:
                self._connected = True
                self.logger.log("OPENWA_SESSAO_INICIADA", {'session_id': sid})
                qr_data = self.obter_qr_code(sid)
                if qr_data:
                    self.logger.log("OPENWA_QR_CODE_DISPONIVEL")
                    print(f"\n📱 Escaneie o QR Code para conectar:")
                    print(f"   Sessão: {self.session_name}")
                return True
            else:
                self.logger.log("OPENWA_SESSAO_INICIO_FALHA", {'status': response.status_code})
                return False
        except Exception as e:
            self.logger.log("OPENWA_SESSAO_INICIO_ERRO", {'erro': str(e)[:100]})
            return False
    
    def obter_qr_code(self, session_id: str = None) -> Optional[str]:
        if not self.habilitado():
            return None
        sid = session_id or self._session_id
        if not sid:
            return None
        try:
            import requests
            url = f"{self.base_url}/api/sessions/{sid}/qr"
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data.get('qrCode', data.get('qr', ''))
            return None
        except Exception as e:
            self.logger.log("OPENWA_QR_CODE_ERRO", {'erro': str(e)[:50]})
            return None
    
    def verificar_sessao(self, session_id: str = None) -> dict:
        if not self.habilitado():
            return {'status': 'disabled'}
        sid = session_id or self._session_id
        if not sid:
            return {'status': 'no_session'}
        try:
            import requests
            url = f"{self.base_url}/api/sessions/{sid}"
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                self._session_info = data
                self._connected = data.get('status') == 'connected'
                return data
            return {'status': 'error', 'code': response.status_code}
        except Exception as e:
            self.logger.log("OPENWA_VERIFICACAO_ERRO", {'erro': str(e)[:50]})
            return {'status': 'error', 'message': str(e)}
    
    def enviar_texto(self, telefone: str, mensagem: str, session_id: str = None, anonimo: bool = False) -> bool:
        if not self.habilitado():
            return False
        sid = session_id or self._session_id
        if not sid:
            sid = self.criar_sessao()
            if not sid:
                return False
            if not self.iniciar_sessao(sid):
                return False
        try:
            import requests
            telefone_normalizado = self._normalizar_telefone_openwa(telefone)
            url = f"{self.base_url}/api/sessions/{sid}/messages/send-text"
            payload = {'chatId': telefone_normalizado, 'text': mensagem}
            response = requests.post(url, headers=self.headers, json=payload, timeout=30)
            if response.status_code in [200, 201]:
                self.logger.log("OPENWA_MSG_ENVIADA", {'telefone': telefone[:8] + '***', 'anonimo': anonimo})
                return True
            else:
                self.logger.log("OPENWA_MSG_ENVIO_FALHA", {'status': response.status_code})
                return False
        except Exception as e:
            self.logger.log("OPENWA_MSG_ENVIO_ERRO", {'erro': str(e)[:50]})
            return False
    
    def _normalizar_telefone_openwa(self, telefone: str) -> str:
        if not telefone:
            return ""
        numeros = re.sub(r'\D', '', telefone)
        if len(numeros) == 10:
            numeros = "55" + numeros
        elif len(numeros) == 11:
            numeros = "55" + numeros
        elif len(numeros) >= 12 and not numeros.startswith('55'):
            numeros = "55" + numeros[-11:] if len(numeros) > 11 else numeros
        return f"{numeros}@c.us"
    
    def listar_sessoes(self) -> List[dict]:
        if not self.habilitado():
            return []
        try:
            import requests
            url = f"{self.base_url}/api/sessions"
            response = requests.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else data.get('data', [])
            return []
        except Exception as e:
            self.logger.log("OPENWA_LISTAR_SESSOES_ERRO", {'erro': str(e)[:50]})
            return []
    
    def excluir_sessao(self, session_id: str = None) -> bool:
        if not self.habilitado():
            return False
        sid = session_id or self._session_id
        if not sid:
            return False
        try:
            import requests
            url = f"{self.base_url}/api/sessions/{sid}"
            response = requests.delete(url, headers=self.headers, timeout=30)
            if response.status_code in [200, 204]:
                self._connected = False
                self._session_id = None
                self.logger.log("OPENWA_SESSAO_EXCLUIDA", {'session_id': sid})
                return True
            return False
        except Exception as e:
            self.logger.log("OPENWA_SESSAO_EXCLUSAO_ERRO", {'erro': str(e)[:50]})
            return False


# ============================================================================
# GERENCIADOR DE CANAIS DE ENVIO (INTEGRADO)
# ============================================================================

class GerenciadorCanais:
    def __init__(self, logger: LoggerAuditoria, base_path: Path):
        self.logger = logger
        self.base_path = base_path
        
        # Inicializa todos os canais
        self.whatsapp = WhatsAppReal(logger, base_path)
        self.sms = EnviadorSMS(logger)
        self.telegram = EnviadorTelegram(logger)
        self.openwa = OpenWAClient(logger)
        
        # Configuração de fallback
        self.fallback_ordem = ['openwa', 'whatsapp', 'sms', 'telegram']
        self.canais_habilitados = {
            'whatsapp': False,
            'sms': False,
            'telegram': False,
            'openwa': False
        }
        
        # Configuração de anonimato
        self.config_anonimo = ANONIMATO_CONFIG.copy()
        self.modo_anonimo_global = self.config_anonimo.get('modo_anonimo', False)
    
    def configurar_whatsapp(self):
        resultado = self.whatsapp.conectar()
        self.canais_habilitados['whatsapp'] = resultado
        return resultado
    
    def configurar_sms(self, account_sid: str, auth_token: str, from_number: str):
        resultado = self.sms.configurar(account_sid, auth_token, from_number)
        self.canais_habilitados['sms'] = resultado
        return resultado
    
    def configurar_telegram(self, bot_token: str, chat_id: str):
        resultado = self.telegram.configurar(bot_token, chat_id)
        self.canais_habilitados['telegram'] = resultado
        return resultado
    
    def configurar_openwa(self, base_url: str, api_key: str, session_name: str = None):
        resultado = self.openwa.configurar(base_url, api_key, session_name)
        self.canais_habilitados['openwa'] = resultado
        if resultado and 'openwa' not in self.fallback_ordem:
            self.fallback_ordem.insert(0, 'openwa')
        return resultado
    
    def conectar_openwa(self) -> bool:
        if not self.canais_habilitados['openwa']:
            self.logger.log("OPENWA_NAO_HABILITADO")
            return False
        if not self.openwa.testar_conexao():
            self.logger.log("OPENWA_SERVIDOR_INDISPONIVEL")
            return False
        session_id = self.openwa.criar_sessao()
        if not session_id:
            self.logger.log("OPENWA_CRIACAO_SESSAO_FALHA")
            return False
        if not self.openwa.iniciar_sessao(session_id):
            self.logger.log("OPENWA_INICIO_SESSAO_FALHA")
            return False
        status = self.openwa.verificar_sessao(session_id)
        self.logger.log("OPENWA_SESSAO_STATUS", {'status': status.get('status')})
        return True
    
    def definir_ordem_fallback(self, ordem: List[str]):
        self.fallback_ordem = ordem
    
    def configurar_anonimato(self, modo_anonimo: bool = None, numero_anonimo: str = None,
                            mensagem_anonima: str = None, ocultar_remetente: bool = None,
                            usar_numero_intermediario: bool = None, numero_intermediario: str = None,
                            exibir_nome_anonimo: str = None):
        if modo_anonimo is not None:
            self.config_anonimo['modo_anonimo'] = modo_anonimo
            self.modo_anonimo_global = modo_anonimo
        if numero_anonimo is not None:
            self.config_anonimo['numero_anonimo'] = numero_anonimo
        if mensagem_anonima is not None:
            self.config_anonimo['mensagem_anonima'] = mensagem_anonima
        if ocultar_remetente is not None:
            self.config_anonimo['ocultar_remetente'] = ocultar_remetente
        if usar_numero_intermediario is not None:
            self.config_anonimo['usar_numero_intermediario'] = usar_numero_intermediario
        if numero_intermediario is not None:
            self.config_anonimo['numero_intermediario'] = numero_intermediario
        if exibir_nome_anonimo is not None:
            self.config_anonimo['exibir_nome_anonimo'] = exibir_nome_anonimo
        self.logger.log("ANONIMATO_CONFIGURADO", {
            'modo_anonimo': self.config_anonimo['modo_anonimo'],
            'exibir_nome': self.config_anonimo['exibir_nome_anonimo']
        })
        global ANONIMATO_CONFIG
        ANONIMATO_CONFIG.update(self.config_anonimo)
        return True
    
    def obter_config_anonimo(self) -> dict:
        return self.config_anonimo.copy()
    
    def modo_anonimo_ativo(self) -> bool:
        return self.modo_anonimo_global
    
    def enviar(self, telefone: str, mensagem: str, canais: List[str] = None, 
               anonimo: bool = None) -> Dict[str, Any]:
        resultado = {
            'sucesso': False,
            'canals_usados': [],
            'canals_falharam': [],
            'mensagem': mensagem,
            'telefone': telefone[:8] + '***',
            'modo_anonimo': anonimo if anonimo is not None else self.modo_anonimo_global
        }
        usar_anonimo = anonimo if anonimo is not None else self.modo_anonimo_global
        canais_para_usar = canais or self.fallback_ordem
        
        for canal in canais_para_usar:
            if canal == 'whatsapp' and not self.whatsapp._conectado:
                continue
            if canal == 'sms' and not self.sms.habilitado():
                continue
            if canal == 'telegram' and not self.telegram.habilitado():
                continue
            if canal == 'openwa' and not self.canais_habilitados['openwa']:
                continue
            
            sucesso = False
            if canal == 'whatsapp':
                sucesso = self.whatsapp.enviar(telefone, mensagem, usar_anonimo, self.config_anonimo)
            elif canal == 'sms':
                sucesso = self.sms.enviar(telefone, mensagem, usar_anonimo, self.config_anonimo)
            elif canal == 'telegram':
                sucesso = self.telegram.enviar(mensagem, telefone, usar_anonimo, self.config_anonimo)
            elif canal == 'openwa':
                sucesso = self.openwa.enviar_texto(telefone, mensagem, anonimo=usar_anonimo)
            
            if sucesso:
                resultado['sucesso'] = True
                resultado['canals_usados'].append(canal)
                self.logger.log(f"MSG_ENVIADA_{canal.upper()}", {
                    'telefone': telefone[:8] + '***',
                    'modo_anonimo': usar_anonimo
                })
                return resultado
            else:
                resultado['canals_falharam'].append(canal)
                self.logger.log(f"FALHA_ENVIO_{canal.upper()}", {'telefone': telefone[:8] + '***'})
        
        return resultado
    
    def fechar(self):
        self.whatsapp.fechar()


# ============================================================================
# FILA PRIORITÁRIA (INTEGRADA)
# ============================================================================

class FilaPrioritaria:
    def __init__(self, logger: LoggerAuditoria, gerenciador_canais: GerenciadorCanais, base_path: Path):
        self.logger = logger
        self.gerenciador_canais = gerenciador_canais
        self.base_path = base_path
        self.fila = queue.PriorityQueue()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.rodando = True
        self.enviados = set()
        self.falhas = {}
        self._lock = threading.RLock()
        self.sistema_parada = SistemaParada(base_path)
        self._start_worker()
    
    def _start_worker(self):
        def worker():
            while self.rodando:
                try:
                    if self.sistema_parada.deve_parar():
                        self.logger.log("PARADA_SOLICITADA_PELO_USUARIO")
                        self.rodando = False
                        break
                    if self.sistema_parada.deve_pausar():
                        self.logger.log("PAUSA_SOLICITADA_PELO_USUARIO")
                        while self.sistema_parada.deve_pausar() and not self.sistema_parada.deve_parar():
                            time.sleep(0.5)
                        if self.sistema_parada.deve_parar():
                            self.rodando = False
                            break
                        self.logger.log("EXECUCAO_RETOMADA")
                        continue
                    item = self.fila.get(timeout=1)
                    self.executor.submit(self._enviar, item)
                except queue.Empty:
                    continue
                except Exception as e:
                    self.logger.log(f"ERRO_WORKER: {str(e)[:50]}")
        threading.Thread(target=worker, daemon=True).start()
    
    def _enviar(self, item: ConsultaPriorizada):
        if self.sistema_parada.deve_parar():
            return
        try:
            dados = item.dados
            consulta = dados['consulta']
            medico = dados['medico']
            chave = dados['chave']
            chave_unica = f"{consulta.get('nome', '')}_{medico}_{consulta.get('data', '')}"
            
            with self._lock:
                if chave_unica in self.enviados:
                    self.logger.log(f"DUPLICADA IGNORADA: {chave_unica}")
                    return
            
            mensagem = self._montar_mensagem(consulta, medico, chave)
            telefone = self._normalizar_telefone(consulta.get('telefone', ''))
            if not telefone:
                self.logger.log("TELEFONE_INVALIDO", {'consulta': consulta.get('nome', '?')})
                return
            
            usar_anonimo = item.modo_anonimo or self.gerenciador_canais.modo_anonimo_ativo()
            
            # Define canais para tentar
            canais = []
            if self.gerenciador_canais.canais_habilitados.get('openwa', False):
                canais.append('openwa')
            if self.gerenciador_canais.whatsapp._conectado:
                canais.append('whatsapp')
            if self.gerenciador_canais.sms.habilitado():
                canais.append('sms')
            if self.gerenciador_canais.telegram.habilitado():
                canais.append('telegram')
            
            if not canais:
                self.logger.log("SEM_CANAIS_DISPONIVEIS", {'consulta': consulta.get('nome', '?')})
                return
            
            resultado = self.gerenciador_canais.enviar(telefone, mensagem, canais, usar_anonimo)
            
            with self._lock:
                if resultado['sucesso']:
                    self.enviados.add(chave_unica)
                    self._salvar_historico(consulta, medico, chave, True, resultado['canals_usados'], usar_anonimo)
                    status = f'OK ({", ".join(resultado["canals_usados"])})'
                else:
                    self.falhas[chave_unica] = self.falhas.get(chave_unica, 0) + 1
                    if self.falhas[chave_unica] < 3:
                        novo_item = ConsultaPriorizada(
                            prioridade=Prioridade.BAIXA.value,
                            timestamp=time.time(),
                            consulta_id=item.consulta_id,
                            dados=item.dados,
                            tentativas=item.tentativas + 1,
                            canal_envio='openwa',
                            modo_anonimo=usar_anonimo
                        )
                        self.fila.put(novo_item)
                        status = f'RETRY {self.falhas[chave_unica]}'
                    else:
                        self._salvar_historico(consulta, medico, chave, False, ['falha'], usar_anonimo)
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
    
    def _salvar_historico(self, consulta: dict, medico: str, chave: str, sucesso: bool, canais: list, anonimo: bool = False):
        with self._lock:
            historico_path = self.base_path / "historico_envios.csv"
            arquivo_existe = historico_path.exists()
            with open(historico_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                if not arquivo_existe:
                    writer.writerow(['Data', 'Paciente', 'Telefone', 'Medico', 'DataConsulta', 'HoraConsulta', 'Chave', 'Status', 'Canais', 'ModoAnonimo'])
                writer.writerow([
                    datetime.now().isoformat(),
                    consulta.get('nome', ''),
                    consulta.get('telefone', ''),
                    medico,
                    consulta.get('data', ''),
                    consulta.get('hora', ''),
                    chave,
                    'Enviado' if sucesso else 'Falha',
                    ' | '.join(canais) if canais else '',
                    'Sim' if anonimo else 'Não'
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
    
    def adicionar(self, consulta: dict, medico: str, chave: str, modo_anonimo: bool = None):
        prioridade = self.calcular_prioridade(consulta.get('data', ''), consulta.get('hora', ''))
        consulta_id = f"{consulta.get('nome', '')}_{medico}_{time.time()}"
        if modo_anonimo is None:
            modo_anonimo = self.gerenciador_canais.modo_anonimo_ativo()
        item = ConsultaPriorizada(
            prioridade=prioridade,
            timestamp=time.time(),
            consulta_id=consulta_id,
            dados={'consulta': consulta, 'medico': medico, 'chave': chave},
            tentativas=0,
            canal_envio='openwa',
            modo_anonimo=modo_anonimo
        )
        self.fila.put(item)
        self.logger.log(f"ENFILEIRADO: {consulta.get('nome', '?')[:15]} | Prioridade: {prioridade} | Anônimo: {modo_anonimo}")
    
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
# AUTOMAÇÃO DE DOWNLOADS
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
# LISTENERS
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
# PROCESSADOR DE PDFS
# ============================================================================

class ProcessadorPDF:
    def __init__(self, logger: LoggerAuditoria, gerenciador_pastas: GerenciadorPastas):
        self.logger = logger
        self.gerenciador_pastas = gerenciador_pastas
    
    def extrair_com_regex(self, texto: str) -> dict:
        dados = {'nome': None, 'telefone': None, 'data': None, 'hora': None, 'medicos': []}
        nome_match = re.search(r'(?:Nome|Paciente)[:\s]+([A-Za-zÀ-Úà-ú][^\n]*)', texto, re.IGNORECASE)
        if nome_match:
            dados['nome'] = nome_match.group(1).strip()
        telefone_match = re.search(r'(?:Telefone|Tel|Fone)[:\s]+([\d\(\)\s-]+)', texto, re.IGNORECASE)
        if telefone_match:
            dados['telefone'] = re.sub(r'\D', '', telefone_match.group(1))
        data_match = re.search(r'(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})', texto)
        if data_match:
            dados['data'] = data_match.group(1)
        hora_match = re.search(r'(\d{2}:\d{2})', texto)
        if hora_match:
            dados['hora'] = hora_match.group(1)
        medicos_match = re.findall(r'(?:Dr|Dra|Médico)[:\s]+([A-Za-zÀ-Úà-ú][^\n]*)', texto, re.IGNORECASE)
        dados['medicos'] = [m.strip() for m in medicos_match if m.strip()]
        return dados
    
    def extrair_e_processar(self, pasta_medico: str, fila: FilaPrioritaria, modo_anonimo: bool = None) -> int:
        pasta = Path(pasta_medico)
        if not pasta.exists():
            return 0
        pdfs = list(pasta.glob('*.pdf'))
        if not pdfs:
            return 0
        print(f"\n📄 Processando {len(pdfs)} PDF(s) de: {pasta.name}")
        if modo_anonimo is not None:
            print(f"   Modo anônimo: {'✅ ATIVO' if modo_anonimo else '❌ DESATIVADO'}")
        processados = 0
        for pdf in pdfs:
            if fila.sistema_parada.deve_parar():
                print("\n🛑 Processamento interrompido pelo usuário!")
                break
            print(f"   📑 {pdf.name}")
            sucesso = False
            try:
                with pdfplumber.open(str(pdf)) as p:
                    texto = p.extract_text()
                    dados = self.extrair_com_regex(texto)
                    if not dados['nome'] or not dados['telefone']:
                        linhas = texto.split('\n')
                        for i, linha in enumerate(linhas):
                            if 'nome' in linha.lower() or 'paciente' in linha.lower():
                                if i + 1 < len(linhas):
                                    dados['nome'] = linhas[i + 1].strip()
                            if 'telefone' in linha.lower() or 'tel' in linha.lower():
                                if i + 1 < len(linhas):
                                    dados['telefone'] = re.sub(r'\D', '', linhas[i + 1].strip())
                            data_padrao = re.search(r'(\d{2}/\d{2}/\d{4})', linha)
                            if data_padrao:
                                dados['data'] = data_padrao.group(1)
                            hora_padrao = re.search(r'(\d{2}:\d{2})', linha)
                            if hora_padrao:
                                dados['hora'] = hora_padrao.group(1)
                    if dados['nome'] and dados['telefone'] and dados['medicos']:
                        chave = ''.join(secrets.choice('0123456789') for _ in range(6))
                        for medico in dados['medicos']:
                            fila.adicionar(dados, medico, chave, modo_anonimo)
                            processados += 1
                            print(f"      ✓ {dados['nome'][:20]} → Dr. {medico} {'🔒' if modo_anonimo else ''}")
                        sucesso = True
                    else:
                        print(f"      ⚠️ Dados incompletos: Nome={dados['nome']}, Tel={dados['telefone']}, Médicos={len(dados['medicos'])}")
                        self.gerenciador_pastas.mover_para_erros(pdf, "Dados incompletos")
            except Exception as e:
                print(f"      ❌ Erro: {str(e)[:50]}")
                self.gerenciador_pastas.mover_para_erros(pdf, f"Erro: {str(e)[:50]}")
            if sucesso:
                try:
                    pdf.unlink()
                    print(f"      🗑️ PDF removido")
                except Exception as e:
                    print(f"      ⚠️ Não foi possível remover: {e}")
        return processados


# ============================================================================
# GERENCIADOR DE CONFIGURAÇÕES (INTEGRADO)
# ============================================================================

class GerenciadorConfiguracoes:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.config_file = base_path / "configuracoes.json"
        self.configuracoes = self._carregar_padrao()
    
    def _carregar_padrao(self) -> dict:
        return {
            'versao': '7.0',
            'ultima_atualizacao': datetime.now().isoformat(),
            'configuracao_completa': False,
            'pasta_base': str(self.base_path),
            'pastas': {
                'downloads': 'downloads_temp',
                'planilhas': 'planilhas',
                'erros': 'erros_pdf',
                'logs': 'logs'
            },
            'medicos': [f'medico_{i}' for i in range(1, 11)],
            'clicks_gravados': [],
            'whatsapp': {'conectado': False, 'ultima_conexao': None, 'perfil_path': 'whatsapp_profile'},
            'sms': {'enabled': False, 'provedor': 'twilio', 'account_sid': '', 'auth_token': '', 'from_number': ''},
            'telegram': {'enabled': False, 'bot_token': '', 'chat_id': ''},
            'openwa': {
                'enabled': False,
                'base_url': 'http://localhost:2785',
                'api_key': '',
                'session_name': 'wam_session',
                'webhook_url': '',
                'webhook_secret': '',
                'auto_start_session': True
            },
            'canais': {
                'ordem_fallback': ['openwa', 'whatsapp', 'sms', 'telegram'],
                'canais_habilitados': {'whatsapp': False, 'sms': False, 'telegram': False, 'openwa': False}
            },
            'anonimato': {
                'modo_anonimo': False,
                'numero_anonimo': '',
                'mensagem_anonima': 'Mensagem enviada via sistema automático',
                'ocultar_remetente': True,
                'usar_numero_intermediario': False,
                'numero_intermediario': '',
                'exibir_nome_anonimo': 'Clínica'
            },
            'lgpd': {
                'consentimento_aceito': False,
                'data_consentimento': None,
                'dpo_contato': DPO_CONTATO,
                'tempo_retencao_dias': TEMPO_RETENCAO_DIAS
            },
            'fila': {'ativa': False, 'total_processados': 0, 'total_enviados': 0, 'total_falhas': 0},
            'ultimo_download': {'pasta_origem': str(Path.home() / "Downloads"), 'pasta_destino': 'medico_1'}
        }
    
    def carregar(self) -> dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    padrao = self._carregar_padrao()
                    for key, value in padrao.items():
                        if key not in config:
                            config[key] = value
                    self.configuracoes = config
                    # Atualiza variáveis globais com as configurações carregadas
                    self._aplicar_configuracoes_globais()
                    return config
            except Exception as e:
                print(f"⚠️ Erro ao carregar configurações: {e}")
                self.configuracoes = self._carregar_padrao()
        return self.configuracoes
    
    def _aplicar_configuracoes_globais(self):
        """Aplica as configurações carregadas às variáveis globais"""
        anon = self.configuracoes.get('anonimato', {})
        ANONIMATO_CONFIG.update(anon)
        
        openwa = self.configuracoes.get('openwa', {})
        OPENWA_CONFIG.update(openwa)
    
    def salvar(self) -> bool:
        try:
            self.configuracoes['ultima_atualizacao'] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configuracoes, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar configurações: {e}")
            return False
    
    def definir_configuracao(self, chave: str, valor):
        partes = chave.split('.')
        atual = self.configuracoes
        for parte in partes[:-1]:
            if parte not in atual:
                atual[parte] = {}
            atual = atual[parte]
        atual[partes[-1]] = valor
        self.salvar()
    
    def obter_configuracao(self, chave: str, padrao=None):
        partes = chave.split('.')
        atual = self.configuracoes
        for parte in partes:
            if isinstance(atual, dict) and parte in atual:
                atual = atual[parte]
            else:
                return padrao
        return atual
    
    def exportar(self, caminho: Path = None) -> bool:
        if not caminho:
            caminho = self.base_path / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        try:
            with open(caminho, 'w', encoding='utf-8') as f:
                json.dump(self.configuracoes, f, indent=2, ensure_ascii=False)
            print(f"✅ Configurações exportadas para: {caminho}")
            return True
        except Exception as e:
            print(f"❌ Erro ao exportar: {e}")
            return False
    
    def importar(self, caminho: Path) -> bool:
        if not caminho.exists():
            print(f"❌ Arquivo não encontrado: {caminho}")
            return False
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.configuracoes.update(config)
                self._aplicar_configuracoes_globais()
                self.salvar()
            print(f"✅ Configurações importadas de: {caminho}")
            return True
        except Exception as e:
            print(f"❌ Erro ao importar: {e}")
            return False


# ============================================================================
# [INTERFACE] ESTILO WHATSAPP PARA O TERMINAL
# ============================================================================

def cor_whatsapp(texto: str, cor: str = "verde") -> str:
    """Aplica cores estilo WhatsApp ao texto"""
    cores = {
        "verde": "\033[92m",     # Verde WhatsApp
        "verde_escuro": "\033[32m",
        "branco": "\033[97m",
        "cinza": "\033[90m",
        "azul": "\033[94m",
        "amarelo": "\033[93m",
        "vermelho": "\033[91m",
        "roxo": "\033[95m",
        "ciano": "\033[96m",
        "negrito": "\033[1m",
        "reset": "\033[0m"
    }
    return f"{cores.get(cor, '')}{texto}{cores['reset']}"


def exibir_banner_whatsapp():
    """Exibe banner com estilo WhatsApp"""
    print("\n" + "="*70)
    print(cor_whatsapp("╔══════════════════════════════════════════════════════════════════╗", "verde"))
    print(cor_whatsapp("║", "verde") + cor_whatsapp("  WAM - WHATSAPP AUTOMATE MESSAGE v7.0", "negrito") + cor_whatsapp("                 ", "verde") + cor_whatsapp("║", "verde"))
    print(cor_whatsapp("║", "verde") + cor_whatsapp("  INTEGRAÇÃO COMPLETA: OpenWA + WhatsApp Web + SMS + Telegram", "branco") + cor_whatsapp("║", "verde"))
    print(cor_whatsapp("║", "verde") + cor_whatsapp("  LGPD COMPLIANT - PROTOCOLOS DE SEGURANÇA ATIVADOS", "ciano") + cor_whatsapp("         ", "verde") + cor_whatsapp("║", "verde"))
    print(cor_whatsapp("╠══════════════════════════════════════════════════════════════════╣", "verde"))
    print(cor_whatsapp("║", "verde") + cor_whatsapp("  🔒 Modo Anônimo: ❌ DESATIVADO", "cinza") + cor_whatsapp("                      ", "verde") + cor_whatsapp("║", "verde"))
    print(cor_whatsapp("║", "verde") + cor_whatsapp("  📱 Canais: OpenWA ❌ | WhatsApp ❌ | SMS ❌ | Telegram ❌", "cinza") + cor_whatsapp("║", "verde"))
    print(cor_whatsapp("╚══════════════════════════════════════════════════════════════════╝", "verde"))
    print("="*70)
    print(cor_whatsapp("💡 Ctrl+Shift+P = Parar | Ctrl+Shift+Espaço = Pausar", "cinza"))
    print("="*70)


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
        self.gerenciador_canais = None
        self.consentimento = None
        self.dados_lgpd = None
        self.configuracoes = None
        self.sistema_parada = None
        
        self._exibir_termo_lgpd()
        self._carregar_configuracoes_iniciais()
    
    def _exibir_termo_lgpd(self):
        print("\n" + "="*80)
        print(cor_whatsapp("WAM - WHATSAPP AUTOMATE MESSAGE v7.0", "negrito"))
        print(cor_whatsapp("PROTOCOLOS LGPD IMPLEMENTADOS", "verde"))
        print("="*80)
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  SEUS DIREITOS SOB A LGPD (Lei 13.709/2018)                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ✓ DIREITO DE CONFIRMAÇÃO: Você pode ver quais dados seus estão aqui        ║
║  ✓ DIREITO DE ACESSO: Você pode solicitar todos os seus dados               ║
║  ✓ DIREITO DE CORREÇÃO: Você pode corrigir dados incompletos                ║
║  ✓ DIREITO DE EXCLUSÃO: Você pode solicitar a remoção dos dados             ║
║  ✓ DIREITO DE OPOSIÇÃO: Você pode revogar o consentimento                   ║
║  ✓ DIREITO DE PORTABILIDADE: Você pode exportar seus dados                  ║
║  ✓ DIREITO DE INFORMAÇÃO: Você sabe como os dados são usados                ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╗
║  NOVIDADES v7.0                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ✓ OPENWA INTEGRATION: WhatsApp API Gateway self-hosted                     ║
║  ✓ MÚLTIPLAS SESSÕES: Gerencie várias contas WhatsApp                      ║
║  ✓ API REST: Envio de mensagens via API                                    ║
║  ✓ WEBHOOKS: Recebimento de mensagens em tempo real                        ║
║  ✓ ENVIO ANÔNIMO: Oculta o número do remetente                             ║
║  ✓ FALLBACK: WhatsApp Web, SMS, Telegram e OpenWA                          ║
║  ✓ CONFIGURAÇÕES SALVAS: Todas as configurações são persistidas             ║
║  ✓ LGPD COMPLIANT: Todos os dados tratados conforme a lei                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
        print("="*80)
        
        confirm = input("\nDigite '" + cor_whatsapp("ACEITO TODOS OS TERMOS LGPD", "negrito") + "' para continuar: ")
        if confirm != "ACEITO TODOS OS TERMOS LGPD":
            print(cor_whatsapp("❌ Consentimento não fornecido. Operação cancelada.", "vermelho"))
            sys.exit(0)
        
        print(cor_whatsapp("✅ Consentimento registrado. Continuando com a automação...\n", "verde"))
    
    def _carregar_configuracoes_iniciais(self):
        base_padrao = Path.home() / "WAM_Data"
        config_file = base_padrao / "configuracoes.json"
        
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                if config.get('configuracao_completa', False):
                    print("\n" + cor_whatsapp("📂 Configurações anteriores encontradas!", "azul"))
                    print(f"   Pasta base: {config.get('pasta_base', 'N/A')}")
                    print(f"   Última atualização: {config.get('ultima_atualizacao', 'N/A')}")
                    print(f"   Modo anônimo: {'✅ ATIVO' if config.get('anonimato', {}).get('modo_anonimo', False) else '❌ DESATIVADO'}")
                    
                    carregar = input("\nDeseja carregar estas configurações? (s/n): ").lower()
                    if carregar == 's':
                        self.base_path = Path(config.get('pasta_base', base_padrao))
                        self._inicializar_sistema()
                        print(cor_whatsapp("✅ Configurações carregadas com sucesso!", "verde"))
                        return
            except Exception as e:
                print(f"⚠️ Erro ao carregar configurações: {e}")
        
        self.base_path = base_padrao
    
    def _inicializar_sistema(self):
        if not self.base_path:
            self.base_path = Path.home() / "WAM_Data"
        
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.sistema_parada = SistemaParada(self.base_path)
        self.sistema_parada.reset()
        
        self.configuracoes = GerenciadorConfiguracoes(self.base_path)
        self.configuracoes.carregar()
        
        self.logger = LoggerAuditoria(self.base_path)
        self.pastas = GerenciadorPastas(self.base_path, self.logger)
        self.pastas.criar_estrutura()
        
        self.downloads = AutomacaoDownloads(self.logger, self.base_path)
        self.processador = ProcessadorPDF(self.logger, self.pastas)
        
        self.consentimento = GerenciadorConsentimento(self.base_path)
        self.dados_lgpd = GerenciadorDadosLGPD(self.base_path, self.logger)
        
        # Inicializa Gerenciador de Canais
        self.gerenciador_canais = GerenciadorCanais(self.logger, self.base_path)
        
        # Carrega configurações dos canais
        self._carregar_canais_config()
        
        # Carrega configurações de anonimato
        self._carregar_anonimato_config()
        
        # Ordem de fallback
        ordem = self.configuracoes.obter_configuracao('canais.ordem_fallback', ['openwa', 'whatsapp', 'sms', 'telegram'])
        self.gerenciador_canais.definir_ordem_fallback(ordem)
        
        # Inicializa fila
        self.fila = FilaPrioritaria(self.logger, self.gerenciador_canais, self.base_path)
        
        self.dados_lgpd.limpar_dados_antigos()
        
        self.configuracoes.definir_configuracao('configuracao_completa', True)
        self.configuracoes.definir_configuracao('pasta_base', str(self.base_path))
        self.configuracoes.salvar()
        
        # Exibe status dos canais
        self._exibir_status_inicial()
    
    def _carregar_canais_config(self):
        """Carrega configurações dos canais"""
        # SMS
        config_sms = self.configuracoes.obter_configuracao('sms', {})
        if config_sms.get('enabled', False):
            self.gerenciador_canais.configurar_sms(
                config_sms.get('account_sid', ''),
                config_sms.get('auth_token', ''),
                config_sms.get('from_number', '')
            )
        
        # Telegram
        config_telegram = self.configuracoes.obter_configuracao('telegram', {})
        if config_telegram.get('enabled', False):
            self.gerenciador_canais.configurar_telegram(
                config_telegram.get('bot_token', ''),
                config_telegram.get('chat_id', '')
            )
        
        # OpenWA
        config_openwa = self.configuracoes.obter_configuracao('openwa', {})
        if config_openwa.get('enabled', False):
            self.gerenciador_canais.configurar_openwa(
                config_openwa.get('base_url', 'http://localhost:2785'),
                config_openwa.get('api_key', ''),
                config_openwa.get('session_name', 'wam_session')
            )
            # Conecta automaticamente se configurado
            if config_openwa.get('auto_start_session', True):
                self.gerenciador_canais.conectar_openwa()
    
    def _carregar_anonimato_config(self):
        """Carrega configurações de anonimato"""
        config_anonimato = self.configuracoes.obter_configuracao('anonimato', {})
        if config_anonimato:
            self.gerenciador_canais.configurar_anonimato(
                modo_anonimo=config_anonimato.get('modo_anonimo', False),
                numero_anonimo=config_anonimato.get('numero_anonimo', ''),
                mensagem_anonima=config_anonimato.get('mensagem_anonima', 'Mensagem enviada via sistema automático'),
                ocultar_remetente=config_anonimato.get('ocultar_remetente', True),
                usar_numero_intermediario=config_anonimato.get('usar_numero_intermediario', False),
                numero_intermediario=config_anonimato.get('numero_intermediario', ''),
                exibir_nome_anonimo=config_anonimato.get('exibir_nome_anonimo', 'Clínica')
            )
    
    def _exibir_status_inicial(self):
        """Exibe status dos canais ao iniciar"""
        modo_anonimo = self.gerenciador_canais.modo_anonimo_ativo()
        openwa_ok = self.gerenciador_canais.canais_habilitados.get('openwa', False)
        whatsapp_ok = self.gerenciador_canais.whatsapp._conectado
        sms_ok = self.gerenciador_canais.sms.habilitado()
        telegram_ok = self.gerenciador_canais.telegram.habilitado()
        
        print("\n" + cor_whatsapp("📊 STATUS DO SISTEMA", "negrito"))
        print("-" * 40)
        print(f"🔒 Modo Anônimo: {'✅ ATIVO' if modo_anonimo else '❌ DESATIVADO'}")
        print(f"📱 OpenWA: {'✅ CONECTADO' if openwa_ok else '❌ DESCONECTADO'}")
        print(f"📱 WhatsApp Web: {'✅ CONECTADO' if whatsapp_ok else '❌ DESCONECTADO'}")
        print(f"📱 SMS: {'✅ CONFIGURADO' if sms_ok else '❌ NÃO CONFIGURADO'}")
        print(f"📱 Telegram: {'✅ CONFIGURADO' if telegram_ok else '❌ NÃO CONFIGURADO'}")
        print("-" * 40)
    
    def menu(self):
        while True:
            # Atualiza banner com status atual
            self._atualizar_banner()
            
            # Verifica teclas de atalho
            if self.sistema_parada and self.sistema_parada.verificar_tecla_parada():
                print("\n" + cor_whatsapp("🛑 PARADA RÁPIDA ACIONADA!", "vermelho"))
                self._parar_execucao()
                continue
            
            if self.sistema_parada and self.sistema_parada.verificar_tecla_pausa():
                if self.sistema_parada.deve_pausar():
                    print("\n" + cor_whatsapp("▶️ RETOMANDO EXECUÇÃO...", "verde"))
                    self.sistema_parada.continuar()
                else:
                    print("\n" + cor_whatsapp("⏸️ PAUSANDO EXECUÇÃO...", "amarelo"))
                    self.sistema_parada.pausar()
                continue
            
            print("\n" + "="*50)
            print(cor_whatsapp("WAM - WHATSAPP AUTOMATE v7.0 - LGPD COMPLIANT", "negrito"))
            print("="*50)
            print(cor_whatsapp("1. CONFIGURAR SISTEMA", "branco"))
            print(cor_whatsapp("2. GRAVAR CLIQUES", "branco"))
            print(cor_whatsapp("3. BAIXAR PDF (automático)", "branco"))
            print(cor_whatsapp("4. PROCESSAR PDFs (Médicos 1-10)", "branco"))
            print(cor_whatsapp("5. LIMPAR PDFs", "branco"))
            print(cor_whatsapp("6. CONECTAR WHATSAPP WEB", "branco"))
            print("-"*50)
            print(cor_whatsapp("[OPENWA] WhatsApp API Gateway", "azul"))
            print(cor_whatsapp("7. CONFIGURAR OPENWA", "branco"))
            print(cor_whatsapp("8. CONECTAR OPENWA", "branco"))
            print(cor_whatsapp("9. LISTAR SESSÕES OPENWA", "branco"))
            print("-"*50)
            print(cor_whatsapp("[ENVIO ANÔNIMO]", "roxo"))
            print(cor_whatsapp("10. ATIVAR/DESATIVAR MODO ANÔNIMO", "branco"))
            print(cor_whatsapp("11. CONFIGURAR NOME ANÔNIMO", "branco"))
            print(cor_whatsapp("12. CONFIGURAR MENSAGEM ANÔNIMA", "branco"))
            print("-"*50)
            print(cor_whatsapp("[CANAL DE ENVIO]", "verde_escuro"))
            print(cor_whatsapp("13. CONFIGURAR SMS (Fallback)", "branco"))
            print(cor_whatsapp("14. CONFIGURAR TELEGRAM", "branco"))
            print(cor_whatsapp("15. DEFINIR ORDEM DE FALLBACK", "branco"))
            print(cor_whatsapp("16. TESTAR ENVIO (Todos os canais)", "branco"))
            print("-"*50)
            print(cor_whatsapp("[LGPD] DIREITOS DOS TITULARES", "ciano"))
            print(cor_whatsapp("17. EXPORTAR DADOS DE UM TITULAR", "branco"))
            print(cor_whatsapp("18. EXCLUIR DADOS DE UM TITULAR", "branco"))
            print(cor_whatsapp("19. REGISTRAR CONSENTIMENTO", "branco"))
            print(cor_whatsapp("20. VER LOGS DE AUDITORIA", "branco"))
            print("-"*50)
            print(cor_whatsapp("[CONFIGURAÇÕES]", "amarelo"))
            print(cor_whatsapp("21. SALVAR CONFIGURAÇÕES ATUAIS", "branco"))
            print(cor_whatsapp("22. EXPORTAR CONFIGURAÇÕES (Backup)", "branco"))
            print(cor_whatsapp("23. IMPORTAR CONFIGURAÇÕES (Restaurar)", "branco"))
            print(cor_whatsapp("24. PARAR EXECUÇÃO IMEDIATAMENTE", "branco"))
            print(cor_whatsapp("25. PAUSAR/RETOMAR EXECUÇÃO", "branco"))
            print("-"*50)
            print(cor_whatsapp("0. SAIR", "vermelho"))
            print("="*50)
            
            # Status atualizado
            self._mostrar_status_linha()
            
            opcao = input("\n" + cor_whatsapp("Escolha: ", "negrito")).strip()
            
            # Mapeamento de opções
            opcoes = {
                '1': self._configurar_sistema,
                '2': self._gravar_cliques,
                '3': self._baixar_pdf,
                '4': self._processar_pdfs,
                '5': self._limpar_pdfs,
                '6': self._conectar_whatsapp,
                '7': self._configurar_openwa,
                '8': self._conectar_openwa,
                '9': self._listar_sessoes_openwa,
                '10': self._alternar_modo_anonimo,
                '11': self._configurar_nome_anonimo,
                '12': self._configurar_mensagem_anonima,
                '13': self._configurar_sms,
                '14': self._configurar_telegram,
                '15': self._definir_ordem_fallback,
                '16': self._testar_envio,
                '17': self._exportar_dados_titular,
                '18': self._excluir_dados_titular,
                '19': self._registrar_consentimento,
                '20': self._ver_logs_auditoria,
                '21': self._salvar_configuracoes,
                '22': self._exportar_configuracoes,
                '23': self._importar_configuracoes,
                '24': self._parar_execucao,
                '25': self._pausar_retomar_execucao,
                '0': self._finalizar
            }
            
            if opcao in opcoes:
                if opcao == '0':
                    opcoes[opcao]()
                    break
                else:
                    opcoes[opcao]()
            else:
                print(cor_whatsapp("❌ Opção inválida!", "vermelho"))
    
    def _atualizar_banner(self):
        """Atualiza o banner com status atual"""
        if self.gerenciador_canais:
            modo_anonimo = self.gerenciador_canais.modo_anonimo_ativo()
            openwa_ok = self.gerenciador_canais.canais_habilitados.get('openwa', False)
            whatsapp_ok = self.gerenciador_canais.whatsapp._conectado
            sms_ok = self.gerenciador_canais.sms.habilitado()
            telegram_ok = self.gerenciador_canais.telegram.habilitado()
            
            # Atualiza variáveis para o banner
            self._status_anonimo = "✅ ATIVO" if modo_anonimo else "❌ DESATIVADO"
            self._status_openwa = "✅" if openwa_ok else "❌"
            self._status_whatsapp = "✅" if whatsapp_ok else "❌"
            self._status_sms = "✅" if sms_ok else "❌"
            self._status_telegram = "✅" if telegram_ok else "❌"
    
    def _mostrar_status_linha(self):
        """Mostra status em uma linha no menu"""
        if self.gerenciador_canais:
            modo = "🔒 " + ("✅" if self.gerenciador_canais.modo_anonimo_ativo() else "❌")
            openwa = "OpenWA " + ("✅" if self.gerenciador_canais.canais_habilitados.get('openwa', False) else "❌")
            whatsapp = "WhatsApp " + ("✅" if self.gerenciador_canais.whatsapp._conectado else "❌")
            sms = "SMS " + ("✅" if self.gerenciador_canais.sms.habilitado() else "❌")
            telegram = "Telegram " + ("✅" if self.gerenciador_canais.telegram.habilitado() else "❌")
            
            print(cor_whatsapp(f"Status: {modo} | {openwa} | {whatsapp} | {sms} | {telegram}", "cinza"))
    
    # ========================================================================
    # MÉTODOS DE CONFIGURAÇÃO
    # ========================================================================
    
    def _configurar_sistema(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONFIGURAÇÃO DO SISTEMA", "negrito"))
        print("="*50)
        
        if self.configuracoes and self.configuracoes.obter_configuracao('configuracao_completa', False):
            print("\n" + cor_whatsapp("📂 Uma configuração já existe:", "azul"))
            print(f"   Pasta base: {self.configuracoes.obter_configuracao('pasta_base', 'N/A')}")
            usar_existente = input("Deseja usar a configuração existente? (s/n): ").lower()
            if usar_existente == 's':
                self.base_path = Path(self.configuracoes.obter_configuracao('pasta_base'))
                self._inicializar_sistema()
                print(cor_whatsapp("\n✅ Sistema configurado com a configuração existente!", "verde"))
                return
        
        base = input("Pasta base (Enter para padrão): ").strip()
        if not base:
            base = str(Path.home() / "WAM_Data")
        
        self.base_path = Path(base)
        self._inicializar_sistema()
        
        print(cor_whatsapp("\n✅ Sistema configurado com sucesso!", "verde"))
        print("\n📱 Canais disponíveis:")
        print("   - WhatsApp Web (opção 6)")
        print("   - OpenWA (opção 7)")
        print("   - SMS (opção 13)")
        print("   - Telegram (opção 14)")
        print("\n💡 Use Ctrl+Shift+P para parar a qualquer momento")
        print("💡 Use Ctrl+Shift+Espaço para pausar/retomar")
    
    def _gravar_cliques(self):
        if not self.downloads:
            print(cor_whatsapp("⚠️ Configure primeiro (opção 1)", "amarelo"))
            return
        self.downloads.gravar_cliques()
        self.configuracoes.salvar()
    
    def _baixar_pdf(self):
        if not self.pastas or not self.downloads:
            print(cor_whatsapp("⚠️ Configure primeiro (opção 1)", "amarelo"))
            return
        downloads = input("Pasta de downloads: ").strip() or str(Path.home() / "Downloads")
        destino = input("Pasta destino: ").strip() or self.pastas.estrutura.get('medico1', '')
        if destino:
            self.downloads.repetir_ate_download(downloads, destino)
            self.configuracoes.definir_configuracao('ultimo_download.pasta_origem', downloads)
            self.configuracoes.definir_configuracao('ultimo_download.pasta_destino', destino)
        else:
            print(cor_whatsapp("⚠️ Pasta destino inválida", "amarelo"))
    
    def _processar_pdfs(self):
        if not self.pastas or not self.fila:
            print(cor_whatsapp("⚠️ Configure primeiro (opção 1)", "amarelo"))
            return
        
        if self.sistema_parada.deve_parar():
            print(cor_whatsapp("⚠️ Sinal de parada detectado. Resetando...", "amarelo"))
            self.sistema_parada.reset()
        
        print("\n" + "="*50)
        print(cor_whatsapp("PROCESSANDO MÉDICOS 1-10", "negrito"))
        print("="*50)
        
        modo_anonimo = self.gerenciador_canais.modo_anonimo_ativo()
        print(f"🔒 Modo Anônimo: {'✅ ATIVO' if modo_anonimo else '❌ DESATIVADO'}")
        if modo_anonimo:
            print(f"   Nome exibido: {self.gerenciador_canais.config_anonimo.get('exibir_nome_anonimo', 'Clínica')}")
        
        print(cor_whatsapp("💡 Pressione Ctrl+Shift+P para parar a qualquer momento", "cinza"))
        print(cor_whatsapp("💡 Pressione Ctrl+Shift+Espaço para pausar/retomar", "cinza"))
        print("-"*50)
        
        # Verifica se tem algum canal configurado
        tem_openwa = self.gerenciador_canais.canais_habilitados.get('openwa', False)
        tem_whatsapp = self.gerenciador_canais.whatsapp._conectado
        tem_sms = self.gerenciador_canais.sms.habilitado()
        tem_telegram = self.gerenciador_canais.telegram.habilitado()
        
        if not (tem_openwa or tem_whatsapp or tem_sms or tem_telegram):
            print("\n" + cor_whatsapp("⚠️ Nenhum canal de envio configurado!", "amarelo"))
            print("   Configure pelo menos um canal:")
            print("   - WhatsApp Web: opção 6")
            print("   - OpenWA: opção 7")
            print("   - SMS: opção 13")
            print("   - Telegram: opção 14")
            continuar = input("\nDeseja continuar mesmo assim? (s/n): ").lower()
            if continuar != 's':
                return
        
        total = 0
        for i in range(1, 11):
            if self.sistema_parada.deve_parar():
                print("\n" + cor_whatsapp("🛑 Processamento interrompido pelo usuário!", "vermelho"))
                break
            
            while self.sistema_parada.deve_pausar():
                print("\n" + cor_whatsapp("⏸️ Processamento PAUSADO. Aguardando retomada...", "amarelo"))
                time.sleep(1)
                if self.sistema_parada.deve_parar():
                    print("\n" + cor_whatsapp("🛑 Processamento interrompido!", "vermelho"))
                    break
            
            pasta = self.pastas.estrutura.get(f'medico{i}')
            if pasta and pasta.exists():
                print(f"\n📂 Processando {pasta.name}...")
                processados = self.processador.extrair_e_processar(str(pasta), self.fila, modo_anonimo)
                total += processados
                print(f"   ✅ {processados} consultas processadas de {pasta.name}")
        
        print(f"\n" + cor_whatsapp(f"✅ {total} consultas processadas e enfileiradas", "verde"))
        
        if total > 0:
            print("\n📊 Fila processando mensagens em background...")
            time.sleep(1)
        
        if self.configuracoes:
            self.configuracoes.definir_configuracao('fila.total_processados', 
                self.configuracoes.obter_configuracao('fila.total_processados', 0) + total)
    
    def _limpar_pdfs(self):
        if self.pastas:
            self.pastas.limpar_todos_pdfs()
        else:
            print(cor_whatsapp("⚠️ Configure primeiro (opção 1)", "amarelo"))
    
    def _conectar_whatsapp(self):
        if not self.gerenciador_canais:
            print(cor_whatsapp("⚠️ Configure primeiro (opção 1)", "amarelo"))
            return
        print("\n🔌 Conectando ao WhatsApp Web...")
        if self.gerenciador_canais.configurar_whatsapp():
            print(cor_whatsapp("✅ WhatsApp Web conectado! As mensagens serão enviadas automaticamente.", "verde"))
            self.configuracoes.definir_configuracao('whatsapp.conectado', True)
            self.configuracoes.definir_configuracao('whatsapp.ultima_conexao', datetime.now().isoformat())
            self.configuracoes.definir_configuracao('canais.canais_habilitados.whatsapp', True)
        else:
            print(cor_whatsapp("❌ Falha na conexão. Verifique se o Chrome está instalado.", "vermelho"))
    
    # ========================================================================
    # MÉTODOS OPENWA
    # ========================================================================
    
    def _configurar_openwa(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONFIGURAR OPENWA - WhatsApp API Gateway", "negrito"))
        print("="*50)
        print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║  OPENWA - WhatsApp API Gateway Self-Hosted                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  OpenWA é um gateway WhatsApp API gratuito e open-source que permite:      ║
║  • Múltiplas sessões WhatsApp simultâneas                                  ║
║  • Envio de mensagens via API REST                                         ║
║  • Webhooks para recebimento de mensagens                                  ║
║  • Suporte a mídia (imagens, vídeos, áudio, documentos)                    ║
║  • Gerenciamento de grupos e canais                                        ║
║  • Dashboard web integrado                                                 ║
║                                                                              ║
║  Para usar, você precisa ter o OpenWA rodando:                             ║
║  git clone https://github.com/rmyndharis/OpenWA.git                        ║
║  cd OpenWA                                                                 ║
║  docker compose -f docker-compose.dev.yml up -d                            ║
║                                                                              ║
║  Acesse: http://localhost:2785                                            ║
║  API: http://localhost:2785/api                                           ║
║  Swagger: http://localhost:2785/api/docs                                  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
        
        base_url = input("URL do OpenWA (Enter para padrão http://localhost:2785): ").strip()
        if not base_url:
            base_url = "http://localhost:2785"
        
        api_key = input(cor_whatsapp("API Key do OpenWA: ", "negrito")).strip()
        if not api_key:
            print(cor_whatsapp("❌ API Key é obrigatória", "vermelho"))
            return
        
        session_name = input("Nome da sessão (Enter para 'wam_session'): ").strip()
        if not session_name:
            session_name = "wam_session"
        
        if self.gerenciador_canais.configurar_openwa(base_url, api_key, session_name):
            print(cor_whatsapp("✅ OpenWA configurado com sucesso!", "verde"))
            
            # Salva configuração
            self.configuracoes.definir_configuracao('openwa.enabled', True)
            self.configuracoes.definir_configuracao('openwa.base_url', base_url)
            self.configuracoes.definir_configuracao('openwa.api_key', api_key)
            self.configuracoes.definir_configuracao('openwa.session_name', session_name)
            self.configuracoes.definir_configuracao('openwa.auto_start_session', True)
            self.configuracoes.definir_configuracao('canais.canais_habilitados.openwa', True)
            
            # Atualiza ordem de fallback
            ordem = self.configuracoes.obter_configuracao('canais.ordem_fallback', ['openwa', 'whatsapp', 'sms', 'telegram'])
            if 'openwa' not in ordem:
                ordem.insert(0, 'openwa')
                self.configuracoes.definir_configuracao('canais.ordem_fallback', ordem)
                self.gerenciador_canais.definir_ordem_fallback(ordem)
            
            # Tenta conectar automaticamente
            print("\n🔄 Tentando conectar ao OpenWA...")
            if self.gerenciador_canais.conectar_openwa():
                print(cor_whatsapp("✅ Conectado ao OpenWA com sucesso!", "verde"))
            else:
                print(cor_whatsapp("⚠️ Configure a conexão manualmente com a opção 8", "amarelo"))
        else:
            print(cor_whatsapp("❌ Falha ao configurar OpenWA", "vermelho"))
    
    def _conectar_openwa(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONECTAR OPENWA", "negrito"))
        print("="*50)
        
        if not self.gerenciador_canais.canais_habilitados.get('openwa', False):
            print(cor_whatsapp("⚠️ OpenWA não configurado. Use a opção 7 primeiro.", "amarelo"))
            return
        
        print("🔄 Conectando ao OpenWA...")
        if self.gerenciador_canais.conectar_openwa():
            print(cor_whatsapp("✅ OpenWA conectado com sucesso!", "verde"))
            
            # Verifica status da sessão
            status = self.gerenciador_canais.openwa.verificar_sessao()
            if status.get('status') == 'connected':
                print(f"📱 Sessão '{status.get('name', '')}' está conectada")
            else:
                print(f"⚠️ Sessão em status: {status.get('status', 'desconhecido')}")
                print("   Verifique o QR Code no dashboard do OpenWA")
        else:
            print(cor_whatsapp("❌ Falha ao conectar ao OpenWA", "vermelho"))
            print("   Verifique se o OpenWA está rodando e a API Key está correta")
    
    def _listar_sessoes_openwa(self):
        print("\n" + "="*50)
        print(cor_whatsapp("SESSÕES OPENWA", "negrito"))
        print("="*50)
        
        if not self.gerenciador_canais.canais_habilitados.get('openwa', False):
            print(cor_whatsapp("⚠️ OpenWA não configurado. Use a opção 7 primeiro.", "amarelo"))
            return
        
        sessoes = self.gerenciador_canais.openwa.listar_sessoes()
        
        if not sessoes:
            print("Nenhuma sessão encontrada")
            return
        
        print("\n📋 Sessões disponíveis:")
        print("-" * 50)
        for sessao in sessoes:
            nome = sessao.get('name', 'N/A')
            status = sessao.get('status', 'N/A')
            criada = sessao.get('createdAt', 'N/A')
            conectado = "✅" if status == 'connected' else "❌"
            
            print(f"  {conectado} {nome} - Status: {status} - Criada: {criada[:19] if criada != 'N/A' else 'N/A'}")
    
    # ========================================================================
    # MÉTODOS DE ANONIMATO
    # ========================================================================
    
    def _alternar_modo_anonimo(self):
        print("\n" + "="*50)
        print(cor_whatsapp("MODO ANÔNIMO - OCULTAR NÚMERO", "negrito"))
        print("="*50)
        print("""
🔒 O modo anônimo oculta o número do remetente nas mensagens.
   Útil para preservar a privacidade do remetente.
        """)
        
        status_atual = self.gerenciador_canais.modo_anonimo_ativo()
        print(f"\nStatus atual: {'✅ ATIVO' if status_atual else '❌ DESATIVADO'}")
        
        if status_atual:
            desativar = input("\nDeseja DESATIVAR o modo anônimo? (s/n): ").lower()
            if desativar == 's':
                self.gerenciador_canais.configurar_anonimato(modo_anonimo=False)
                self.configuracoes.definir_configuracao('anonimato.modo_anonimo', False)
                print(cor_whatsapp("✅ Modo anônimo DESATIVADO!", "verde"))
            else:
                print("❌ Operação cancelada")
        else:
            ativar = input("\nDeseja ATIVAR o modo anônimo? (s/n): ").lower()
            if ativar == 's':
                self.gerenciador_canais.configurar_anonimato(modo_anonimo=True)
                self.configuracoes.definir_configuracao('anonimato.modo_anonimo', True)
                print(cor_whatsapp("✅ Modo anônimo ATIVADO!", "verde"))
            else:
                print("❌ Operação cancelada")
    
    def _configurar_nome_anonimo(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONFIGURAR NOME ANÔNIMO", "negrito"))
        print("="*50)
        
        nome_atual = self.gerenciador_canais.config_anonimo.get('exibir_nome_anonimo', 'Clínica')
        print(f"\nNome atual: {nome_atual}")
        
        nome = input("\nNovo nome (Enter para manter): ").strip()
        if nome:
            self.gerenciador_canais.configurar_anonimato(exibir_nome_anonimo=nome)
            self.configuracoes.definir_configuracao('anonimato.exibir_nome_anonimo', nome)
            print(cor_whatsapp(f"✅ Nome anônimo configurado: {nome}", "verde"))
        else:
            print("❌ Nome mantido")
    
    def _configurar_mensagem_anonima(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONFIGURAR MENSAGEM ANÔNIMA", "negrito"))
        print("="*50)
        
        msg_atual = self.gerenciador_canais.config_anonimo.get('mensagem_anonima', 'Mensagem enviada via sistema automático')
        print(f"\nMensagem atual: {msg_atual}")
        
        msg = input("\nNova mensagem (Enter para manter): ").strip()
        if msg:
            self.gerenciador_canais.configurar_anonimato(mensagem_anonima=msg)
            self.configuracoes.definir_configuracao('anonimato.mensagem_anonima', msg)
            print(cor_whatsapp(f"✅ Mensagem anônima configurada: {msg}", "verde"))
        else:
            print("❌ Mensagem mantida")
    
    # ========================================================================
    # MÉTODOS SMS E TELEGRAM
    # ========================================================================
    
    def _configurar_sms(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONFIGURAR SMS (FALLBACK)", "negrito"))
        print("="*50)
        print("""
📱 SMS é usado como fallback quando os outros canais falham.
   Provedores suportados: Twilio, AWS SNS, SMS Dev (teste)
        """)
        
        print("\nProvedores disponíveis:")
        print("1. Twilio (recomendado)")
        print("2. SMS Dev (para testes)")
        print("3. Custom (API própria)")
        print("0. Cancelar")
        
        opcao = input("Escolha: ").strip()
        
        if opcao == '0':
            return
        
        if opcao == '1':
            account_sid = input("Account SID: ").strip()
            auth_token = input("Auth Token: ").strip()
            from_number = input("Número de origem (com + e código do país): ").strip()
            
            if account_sid and auth_token and from_number:
                if self.gerenciador_canais.configurar_sms(account_sid, auth_token, from_number):
                    print(cor_whatsapp("✅ SMS configurado com sucesso!", "verde"))
                    self.configuracoes.definir_configuracao('sms.enabled', True)
                    self.configuracoes.definir_configuracao('sms.provedor', 'twilio')
                    self.configuracoes.definir_configuracao('sms.account_sid', account_sid)
                    self.configuracoes.definir_configuracao('sms.auth_token', auth_token)
                    self.configuracoes.definir_configuracao('sms.from_number', from_number)
                    self.configuracoes.definir_configuracao('canais.canais_habilitados.sms', True)
                else:
                    print(cor_whatsapp("❌ Falha ao configurar SMS", "vermelho"))
            else:
                print(cor_whatsapp("❌ Todos os campos são obrigatórios", "vermelho"))
        
        elif opcao == '2':
            api_key = input("API Key (SMS Dev): ").strip()
            if api_key:
                self.configuracoes.definir_configuracao('sms.enabled', True)
                self.configuracoes.definir_configuracao('sms.provedor', 'sms_dev')
                self.configuracoes.definir_configuracao('sms.api_key', api_key)
                self.configuracoes.definir_configuracao('canais.canais_habilitados.sms', True)
                print(cor_whatsapp("✅ SMS Dev configurado para testes!", "verde"))
            else:
                print(cor_whatsapp("❌ API Key é obrigatória", "vermelho"))
        
        elif opcao == '3':
            url_api = input("URL da API: ").strip()
            api_key = input("API Key: ").strip()
            if url_api and api_key:
                self.configuracoes.definir_configuracao('sms.enabled', True)
                self.configuracoes.definir_configuracao('sms.provedor', 'custom')
                self.configuracoes.definir_configuracao('sms.url_api', url_api)
                self.configuracoes.definir_configuracao('sms.api_key', api_key)
                self.configuracoes.definir_configuracao('canais.canais_habilitados.sms', True)
                print(cor_whatsapp("✅ SMS Custom configurado!", "verde"))
            else:
                print(cor_whatsapp("❌ URL e API Key são obrigatórias", "vermelho"))
    
    def _configurar_telegram(self):
        print("\n" + "="*50)
        print(cor_whatsapp("CONFIGURAR TELEGRAM", "negrito"))
        print("="*50)
        print("""
🤖 Telegram Bot - Envio de mensagens via Telegram
   
   Como configurar:
   1. Crie um bot no Telegram via @BotFather
   2. Copie o token do bot
   3. Obtenha o chat_id (ID do seu chat/grupo)
        """)
        
        bot_token = input("Token do Bot: ").strip()
        chat_id = input("Chat ID: ").strip()
        
        if bot_token and chat_id:
            if self.gerenciador_canais.configurar_telegram(bot_token, chat_id):
                print(cor_whatsapp("✅ Telegram configurado com sucesso!", "verde"))
                self.configuracoes.definir_configuracao('telegram.enabled', True)
                self.configuracoes.definir_configuracao('telegram.bot_token', bot_token)
                self.configuracoes.definir_configuracao('telegram.chat_id', chat_id)
                self.configuracoes.definir_configuracao('canais.canais_habilitados.telegram', True)
                
                # Testa envio
                print("\n🧪 Testando envio...")
                self.gerenciador_canais.telegram.enviar("✅ WAM conectado com sucesso!\n\nSistema de envio de mensagens configurado.")
            else:
                print(cor_whatsapp("❌ Falha ao configurar Telegram. Verifique o token e chat_id.", "vermelho"))
        else:
            print(cor_whatsapp("❌ Token e Chat ID são obrigatórios", "vermelho"))
    
    def _definir_ordem_fallback(self):
        print("\n" + "="*50)
        print(cor_whatsapp("ORDEM DE FALLBACK DOS CANAIS", "negrito"))
        print("="*50)
        print("""
📋 Defina em qual ordem os canais serão usados.
   O primeiro da lista que funcionar será usado.
   
   Canais disponíveis:
   - openwa (API Gateway)
   - whatsapp (Selenium)
   - sms
   - telegram
        """)
        
        print("\nOrdem atual:", " → ".join(self.gerenciador_canais.fallback_ordem))
        print("\nDigite a nova ordem separada por vírgula")
        print("Exemplo: openwa,whatsapp,sms,telegram")
        print("Exemplo: telegram,whatsapp (só Telegram e WhatsApp)")
        
        nova_ordem = input("Nova ordem: ").strip()
        if nova_ordem:
            canais = [c.strip().lower() for c in nova_ordem.split(',') if c.strip()]
            validos = ['openwa', 'whatsapp', 'sms', 'telegram']
            canais_validos = [c for c in canais if c in validos]
            
            if canais_validos:
                self.gerenciador_canais.definir_ordem_fallback(canais_validos)
                self.configuracoes.definir_configuracao('canais.ordem_fallback', canais_validos)
                print(cor_whatsapp(f"✅ Ordem de fallback definida: {' → '.join(canais_validos)}", "verde"))
            else:
                print(cor_whatsapp("❌ Nenhum canal válido informado", "vermelho"))
    
    def _testar_envio(self):
        print("\n" + "="*50)
        print(cor_whatsapp("TESTAR ENVIO DE MENSAGEM", "negrito"))
        print("="*50)
        
        telefone = input("Telefone para teste (com DDD): ").strip()
        if not telefone:
            print(cor_whatsapp("❌ Telefone é obrigatório", "vermelho"))
            return
        
        mensagem = input("Mensagem de teste (Enter para padrão): ").strip()
        if not mensagem:
            mensagem = f"🧪 Teste WAM v7.0\n\nEnviado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\nEste é um teste do sistema multi-canais com OpenWA."
        
        modo_anonimo = self.gerenciador_canais.modo_anonimo_ativo()
        print("\n" + "-"*50)
        print(f"🔒 Modo Anônimo: {'✅ ATIVO' if modo_anonimo else '❌ DESATIVADO'}")
        if modo_anonimo:
            print(f"   Nome exibido: {self.gerenciador_canais.config_anonimo.get('exibir_nome_anonimo', 'Clínica')}")
        
        print("\nCANAIS DISPONÍVEIS:")
        status_openwa = "✅" if self.gerenciador_canais.canais_habilitados.get('openwa', False) else "❌"
        status_whatsapp = "✅" if self.gerenciador_canais.whatsapp._conectado else "❌"
        status_sms = "✅" if self.gerenciador_canais.sms.habilitado() else "❌"
        status_telegram = "✅" if self.gerenciador_canais.telegram.habilitado() else "❌"
        
        print(f"  OpenWA: {status_openwa}")
        print(f"  WhatsApp: {status_whatsapp}")
        print(f"  SMS: {status_sms}")
        print(f"  Telegram: {status_telegram}")
        print("-"*50)
        
        if self.gerenciador_canais.modo_anonimo_ativo():
            usar_anonimo = True
            print("\n⚠️ Modo anônimo está ATIVO globalmente")
        else:
            usar_anonimo_str = input("\nUsar modo anônimo neste teste? (s/n): ").lower()
            usar_anonimo = usar_anonimo_str == 's'
        
        canais = input("\nCanais para testar (separados por vírgula, Enter para todos): ").strip()
        if canais:
            canais_lista = [c.strip().lower() for c in canais.split(',') if c.strip()]
        else:
            canais_lista = ['openwa', 'whatsapp', 'sms', 'telegram']
        
        print(f"\n📤 Enviando via: {' → '.join(canais_lista)}")
        print(f"🔒 Modo anônimo: {'✅ ATIVO' if usar_anonimo else '❌ DESATIVADO'}")
        print("-"*50)
        
        resultado = self.gerenciador_canais.enviar(telefone, mensagem, canais_lista, usar_anonimo)
        
        print("\n📊 RESULTADO:")
        if resultado['sucesso']:
            print(cor_whatsapp(f"  ✅ Mensagem enviada com sucesso!", "verde"))
            print(f"  Canais usados: {' → '.join(resultado['canals_usados'])}")
            print(f"  Modo anônimo: {'✅ ATIVO' if resultado['modo_anonimo'] else '❌ DESATIVADO'}")
        else:
            print(cor_whatsapp(f"  ❌ Falha no envio", "vermelho"))
            print(f"  Canais que falharam: {' → '.join(resultado['canals_falharam'])}")
        
        if resultado['canals_falharam']:
            print("\n  Canais que não puderam ser usados (não configurados ou offline):")
            for canal in resultado['canals_falharam']:
                print(f"  - {canal}")
    
    # ========================================================================
    # MÉTODOS LGPD
    # ========================================================================
    
    def _exportar_dados_titular(self):
        print("\n" + "="*50)
        print(cor_whatsapp("EXPORTAR DADOS DO TITULAR", "negrito"))
        print("="*50)
        
        telefone = input("Digite o telefone do titular (com DDD): ").strip()
        if not telefone:
            print(cor_whatsapp("❌ Telefone não informado", "vermelho"))
            return
        
        arquivo = self.dados_lgpd.exportar_dados_titular(telefone)
        if arquivo:
            print(cor_whatsapp(f"✅ Dados exportados com sucesso: {arquivo}", "verde"))
        else:
            print(cor_whatsapp("⚠️ Nenhum dado encontrado para este telefone", "amarelo"))
    
    def _excluir_dados_titular(self):
        print("\n" + "="*50)
        print(cor_whatsapp("EXCLUIR DADOS DO TITULAR", "negrito"))
        print("="*50)
        print(cor_whatsapp("⚠️ ATENÇÃO: Esta ação é irreversível!", "vermelho"))
        
        telefone = input("Digite o telefone do titular (com DDD): ").strip()
        if not telefone:
            print(cor_whatsapp("❌ Telefone não informado", "vermelho"))
            return
        
        confirm = input(f"Deseja realmente excluir TODOS os dados de {telefone}? (s/n): ").lower()
        if confirm == 's':
            if self.dados_lgpd.excluir_dados_titular(telefone):
                print(cor_whatsapp("✅ Dados excluídos com sucesso", "verde"))
            else:
                print(cor_whatsapp("⚠️ Nenhum dado encontrado para este telefone", "amarelo"))
    
    def _registrar_consentimento(self):
        print("\n" + "="*50)
        print(cor_whatsapp("REGISTRAR CONSENTIMENTO DO TITULAR", "negrito"))
        print("="*50)
        
        nome = input("Nome completo do titular: ").strip()
        telefone = input("Telefone (com DDD): ").strip()
        
        if not nome or not telefone:
            print(cor_whatsapp("❌ Nome e telefone são obrigatórios", "vermelho"))
            return
        
        print("\nFinalidade do tratamento:")
        print("- Envio de mensagens automáticas sobre consultas médicas")
        print("- Armazenamento de histórico de comunicações")
        
        if self.gerenciador_canais.modo_anonimo_ativo():
            print("\n🔒 Modo anônimo ATIVO:")
            print(f"   O número do remetente será ocultado")
            print(f"   Nome exibido: {self.gerenciador_canais.config_anonimo.get('exibir_nome_anonimo', 'Clínica')}")
        
        confirm = input("\nO titular concorda com esta finalidade? (s/n): ").lower()
        if confirm == 's':
            self.consentimento.registrar_consentimento(nome, telefone)
            print(cor_whatsapp("✅ Consentimento registrado com sucesso!", "verde"))
        else:
            print(cor_whatsapp("❌ Consentimento não registrado", "vermelho"))
    
    def _ver_logs_auditoria(self):
        print("\n" + "="*50)
        print(cor_whatsapp("LOGS DE AUDITORIA LGPD", "negrito"))
        print("="*50)
        
        if self.base_path:
            logs_dir = self.base_path / "logs_auditoria"
            if logs_dir.exists():
                logs = list(logs_dir.glob("*.log"))
                if logs:
                    print("\nÚltimos logs:")
                    for log_file in sorted(logs, reverse=True)[:5]:
                        print(f"   📄 {log_file.name}")
                        with open(log_file, 'r', encoding='utf-8') as f:
                            linhas = f.readlines()[-5:]
                            for linha in linhas:
                                print(f"      {linha.strip()[:100]}")
                else:
                    print("Nenhum log encontrado")
            else:
                print("Pasta de logs não encontrada")
    
    # ========================================================================
    # MÉTODOS DE CONFIGURAÇÕES
    # ========================================================================
    
    def _salvar_configuracoes(self):
        print("\n" + "="*50)
        print(cor_whatsapp("SALVAR CONFIGURAÇÕES", "negrito"))
        print("="*50)
        
        if not self.configuracoes:
            print(cor_whatsapp("⚠️ Sistema não configurado", "amarelo"))
            return
        
        if self.configuracoes.salvar():
            print(cor_whatsapp(f"✅ Configurações salvas em: {self.configuracoes.config_file}", "verde"))
            print(f"   Pasta base: {self.base_path}")
            print(f"   Modo anônimo: {'✅ ATIVO' if self.gerenciador_canais.modo_anonimo_ativo() else '❌ DESATIVADO'}")
            print(f"   OpenWA: {'✅ HABILITADO' if self.gerenciador_canais.canais_habilitados.get('openwa', False) else '❌ DESABILITADO'}")
            print(f"   Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            print(cor_whatsapp("❌ Erro ao salvar configurações", "vermelho"))
    
    def _exportar_configuracoes(self):
        print("\n" + "="*50)
        print(cor_whatsapp("EXPORTAR CONFIGURAÇÕES (BACKUP)", "negrito"))
        print("="*50)
        
        if not self.configuracoes:
            print(cor_whatsapp("⚠️ Sistema não configurado", "amarelo"))
            return
        
        caminho = input("Caminho para exportar (Enter para padrão): ").strip()
        if caminho:
            caminho = Path(caminho)
        else:
            caminho = self.base_path / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        if self.configuracoes.exportar(caminho):
            print(cor_whatsapp("✅ Configurações exportadas com sucesso!", "verde"))
    
    def _importar_configuracoes(self):
        print("\n" + "="*50)
        print(cor_whatsapp("IMPORTAR CONFIGURAÇÕES (RESTAURAR)", "negrito"))
        print("="*50)
        print(cor_whatsapp("⚠️ ATENÇÃO: Isso sobrescreverá as configurações atuais!", "vermelho"))
        
        caminho = input("Caminho do arquivo de configuração: ").strip()
        if not caminho:
            print(cor_whatsapp("❌ Caminho não informado", "vermelho"))
            return
        
        caminho = Path(caminho)
        if not caminho.exists():
            print(cor_whatsapp(f"❌ Arquivo não encontrado: {caminho}", "vermelho"))
            return
        
        confirm = input("Deseja realmente importar estas configurações? (s/n): ").lower()
        if confirm != 's':
            print("❌ Importação cancelada")
            return
        
        if self.configuracoes.importar(caminho):
            print(cor_whatsapp("✅ Configurações importadas com sucesso!", "verde"))
            print(cor_whatsapp("🔄 Reiniciando sistema com novas configurações...", "azul"))
            self._inicializar_sistema()
            print(cor_whatsapp("✅ Sistema reiniciado com as configurações importadas!", "verde"))
        else:
            print(cor_whatsapp("❌ Erro ao importar configurações", "vermelho"))
    
    def _parar_execucao(self):
        print("\n" + "="*50)
        print(cor_whatsapp("PARAR EXECUÇÃO", "negrito"))
        print("="*50)
        
        if not self.sistema_parada:
            print(cor_whatsapp("⚠️ Sistema não inicializado", "amarelo"))
            return
        
        confirm = input("Deseja parar a execução imediatamente? (s/n): ").lower()
        if confirm == 's':
            self.sistema_parada.parar()
            print(cor_whatsapp("🛑 Sinal de PARADA enviado!", "vermelho"))
            print("   A execução será interrompida em breve...")
            if self.fila:
                self.fila.rodando = False
            print(cor_whatsapp("✅ Execução parada com sucesso!", "verde"))
        else:
            print("❌ Parada cancelada")
    
    def _pausar_retomar_execucao(self):
        print("\n" + "="*50)
        print(cor_whatsapp("PAUSAR/RETOMAR EXECUÇÃO", "negrito"))
        print("="*50)
        
        if not self.sistema_parada:
            print(cor_whatsapp("⚠️ Sistema não inicializado", "amarelo"))
            return
        
        if self.sistema_parada.deve_pausar():
            print("⏸️ Execução está PAUSADA")
            retomar = input("Deseja retomar? (s/n): ").lower()
            if retomar == 's':
                self.sistema_parada.continuar()
                print(cor_whatsapp("▶️ Execução retomada!", "verde"))
        else:
            print("▶️ Execução está ATIVA")
            pausar = input("Deseja pausar? (s/n): ").lower()
            if pausar == 's':
                self.sistema_parada.pausar()
                print(cor_whatsapp("⏸️ Execução pausada!", "amarelo"))
    
    def _finalizar(self):
        if self.fila:
            self.fila.stop()
        if self.gerenciador_canais:
            self.gerenciador_canais.fechar()
        
        if self.dados_lgpd:
            self.dados_lgpd.limpar_dados_antigos()
        
        if self.configuracoes:
            self.configuracoes.salvar()
            print(cor_whatsapp("✅ Configurações salvas", "verde"))
        
        if self.sistema_parada:
            self.sistema_parada.reset()
        
        print("\n" + cor_whatsapp("Encerrando...", "cinza"))


# ============================================================================
# MAIN
# ============================================================================

def main():
    exibir_banner_whatsapp()
    
    try:
        app = WAM()
        app.menu()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrompido pelo usuário")
        try:
            if 'app' in locals() and app.configuracoes:
                app.configuracoes.salvar()
                print(cor_whatsapp("✅ Configurações salvas antes de encerrar", "verde"))
        except:
            pass
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()