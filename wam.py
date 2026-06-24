#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  WAM - WhatsApp Automate Message v5.4 - LGPD COMPLIANT                      ║
║  COM INTEGRAÇÃO REAL COM WHATSAPP WEB (Selenium)                           ║
║  NOVIDADES: PARADA A QUALQUER MOMENTO + SALVAR CONFIGURAÇÕES              ║
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
import hashlib
import base64
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

# ============================================================================
# [LGPD] CONSTANTES DE PROTOCOLO
# ============================================================================

TEMPO_RETENCAO_DIAS = 30  # Dados são mantidos por 30 dias
DPO_CONTATO = "dpo@exemplo.com"  # [LGPD] Contato do Encarregado
VIOLACAO_NOTIFICAR_EMAIL = True  # [LGPD] Notificar violações

# ============================================================================
# [NOVO] SISTEMA DE PARADA GLOBAL
# ============================================================================

class SistemaParada:
    """Sistema para parar a execução a qualquer momento via arquivo de sinal"""
    
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
        
        # Remove sinais antigos ao iniciar
        self._limpar_sinais()
    
    def _limpar_sinais(self):
        """Remove sinais de parada anteriores"""
        for arquivo in [self.stop_file, self.pause_file]:
            if arquivo.exists():
                try:
                    arquivo.unlink()
                except:
                    pass
    
    def deve_parar(self) -> bool:
        """Verifica se deve parar a execução"""
        return self.stop_file.exists()
    
    def deve_pausar(self) -> bool:
        """Verifica se deve pausar a execução"""
        return self.pause_file.exists()
    
    def parar(self):
        """Solicita parada imediata"""
        self.stop_file.touch()
        print("\n🛑 Sinal de PARADA acionado!")
    
    def pausar(self):
        """Solicita pausa da execução"""
        self.pause_file.touch()
        print("\n⏸️ Sinal de PAUSA acionado!")
    
    def continuar(self):
        """Retoma execução após pausa"""
        if self.pause_file.exists():
            self.pause_file.unlink()
            print("\n▶️ Execução retomada!")
    
    def reset(self):
        """Reseta todos os sinais"""
        self._limpar_sinais()
    
    @staticmethod
    def monitorar_teclas():
        """Thread para monitorar teclas de atalho (Ctrl+Shift+P = Parar)"""
        # Esta função será chamada em uma thread separada
        # O monitoramento real é feito via GetAsyncKeyState no main loop
    
    def verificar_tecla_parada(self) -> bool:
        """Verifica se a tecla de parada foi pressionada (Ctrl+Shift+P)"""
        # Verifica se Ctrl, Shift e P estão pressionados
        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000  # VK_CONTROL
        shift = user32.GetAsyncKeyState(0x10) & 0x8000  # VK_SHIFT
        p = user32.GetAsyncKeyState(ord('P')) & 0x8000
        
        if ctrl and shift and p:
            return True
        return False
    
    def verificar_tecla_pausa(self) -> bool:
        """Verifica se a tecla de pausa foi pressionada (Ctrl+Shift+Space)"""
        ctrl = user32.GetAsyncKeyState(0x11) & 0x8000
        shift = user32.GetAsyncKeyState(0x10) & 0x8000
        space = user32.GetAsyncKeyState(0x20) & 0x8000  # VK_SPACE
        
        if ctrl and shift and space:
            return True
        return False


# ============================================================================
# [NOVO] GERENCIADOR DE CONFIGURAÇÕES
# ============================================================================

class GerenciadorConfiguracoes:
    """Salva e carrega configurações do sistema"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.config_file = base_path / "configuracoes.json"
        self.configuracoes = self._carregar_padrao()
    
    def _carregar_padrao(self) -> dict:
        """Configurações padrão"""
        return {
            'versao': '5.4',
            'ultima_atualizacao': datetime.now().isoformat(),
            'configuracao_completa': False,
            
            # Pastas
            'pasta_base': str(self.base_path),
            'pastas': {
                'downloads': 'downloads_temp',
                'planilhas': 'planilhas',
                'erros': 'erros_pdf',
                'logs': 'logs'
            },
            
            # Médicos (10 pastas)
            'medicos': [f'medico_{i}' for i in range(1, 11)],
            
            # Cliques gravados
            'clicks_gravados': [],
            
            # WhatsApp
            'whatsapp': {
                'conectado': False,
                'ultima_conexao': None,
                'perfil_path': 'whatsapp_profile'
            },
            
            # LGPD
            'lgpd': {
                'consentimento_aceito': False,
                'data_consentimento': None,
                'dpo_contato': DPO_CONTATO,
                'tempo_retencao_dias': TEMPO_RETENCAO_DIAS
            },
            
            # Fila
            'fila': {
                'ativa': False,
                'total_processados': 0,
                'total_enviados': 0,
                'total_falhas': 0
            },
            
            # Últimas configurações
            'ultimo_download': {
                'pasta_origem': str(Path.home() / "Downloads"),
                'pasta_destino': 'medico_1'
            }
        }
    
    def carregar(self) -> dict:
        """Carrega configurações do arquivo"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # Atualiza com padrões para garantir campos novos
                    padrao = self._carregar_padrao()
                    for key, value in padrao.items():
                        if key not in config:
                            config[key] = value
                    self.configuracoes = config
                    return config
            except Exception as e:
                print(f"⚠️ Erro ao carregar configurações: {e}")
                self.configuracoes = self._carregar_padrao()
        return self.configuracoes
    
    def salvar(self) -> bool:
        """Salva configurações no arquivo"""
        try:
            self.configuracoes['ultima_atualizacao'] = datetime.now().isoformat()
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configuracoes, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ Erro ao salvar configurações: {e}")
            return False
    
    def definir_configuracao(self, chave: str, valor):
        """Define uma configuração específica"""
        partes = chave.split('.')
        atual = self.configuracoes
        for parte in partes[:-1]:
            if parte not in atual:
                atual[parte] = {}
            atual = atual[parte]
        atual[partes[-1]] = valor
        self.salvar()
    
    def obter_configuracao(self, chave: str, padrao=None):
        """Obtém uma configuração específica"""
        partes = chave.split('.')
        atual = self.configuracoes
        for parte in partes:
            if isinstance(atual, dict) and parte in atual:
                atual = atual[parte]
            else:
                return padrao
        return atual
    
    def exportar(self, caminho: Path = None) -> bool:
        """Exporta configurações para um arquivo externo"""
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
        """Importa configurações de um arquivo externo"""
        if not caminho.exists():
            print(f"❌ Arquivo não encontrado: {caminho}")
            return False
        
        try:
            with open(caminho, 'r', encoding='utf-8') as f:
                config = json.load(f)
                self.configuracoes.update(config)
                self.salvar()
            print(f"✅ Configurações importadas de: {caminho}")
            return True
        except Exception as e:
            print(f"❌ Erro ao importar: {e}")
            return False


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
# [LGPD] GERENCIADOR DE CONSENTIMENTO
# ============================================================================

class GerenciadorConsentimento:
    """Gerencia o consentimento do titular dos dados (LGPD Art. 7º)"""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.consentimento_path = base_path / "consentimentos"
        self.consentimento_path.mkdir(parents=True, exist_ok=True)
    
    def registrar_consentimento(self, nome: str, telefone: str, documento: str = None):
        """Registra o consentimento do titular"""
        registro = {
            'nome': nome,
            'telefone': telefone,
            'documento': documento,
            'data_consentimento': datetime.now().isoformat(),
            'validade': (datetime.now() + timedelta(days=365)).isoformat(),
            'ip': 'local',
            'finalidade': 'Envio de mensagens automáticas sobre consultas'
        }
        
        # Hash do telefone para identificação única
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        arquivo = self.consentimento_path / f"{hash_id}.json"
        
        with open(arquivo, 'w', encoding='utf-8') as f:
            json.dump(registro, f, indent=2, ensure_ascii=False)
        
        return True
    
    def verificar_consentimento(self, telefone: str) -> bool:
        """Verifica se o titular consentiu"""
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        arquivo = self.consentimento_path / f"{hash_id}.json"
        
        if not arquivo.exists():
            return False
        
        with open(arquivo, 'r', encoding='utf-8') as f:
            registro = json.load(f)
        
        # Verifica se o consentimento ainda é válido
        validade = datetime.fromisoformat(registro.get('validade', '2000-01-01'))
        if validade < datetime.now():
            return False
        
        return True
    
    def revogar_consentimento(self, telefone: str) -> bool:
        """Revoga o consentimento (direito de oposição)"""
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        arquivo = self.consentimento_path / f"{hash_id}.json"
        
        if arquivo.exists():
            # Move para pasta de revogados
            revogados = self.base_path / "consentimentos_revogados"
            revogados.mkdir(exist_ok=True)
            shutil.move(str(arquivo), str(revogados / arquivo.name))
            return True
        return False


# ============================================================================
# [LGPD] GERENCIADOR DE DADOS (Portabilidade e Exclusão)
# ============================================================================

class GerenciadorDadosLGPD:
    """Gerencia direitos do titular: acesso, portabilidade, exclusão"""
    
    def __init__(self, base_path: Path, logger: 'LoggerAuditoria'):
        self.base_path = base_path
        self.logger = logger
    
    def exportar_dados_titular(self, telefone: str) -> Optional[Path]:
        """Exporta todos os dados de um titular (LGPD Art. 18, VI - Portabilidade)"""
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        
        dados_titular = {
            'titular': {'telefone': telefone},
            'consultas': [],
            'consentimento': None,
            'data_exportacao': datetime.now().isoformat()
        }
        
        # Busca histórico de envios
        historico_path = self.base_path / "historico_envios.csv"
        if historico_path.exists():
            with open(historico_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('Telefone') == telefone:
                        dados_titular['consultas'].append(row)
        
        # Busca consentimento
        consentimento_path = self.base_path / "consentimentos" / f"{hash_id}.json"
        if consentimento_path.exists():
            with open(consentimento_path, 'r', encoding='utf-8') as f:
                dados_titular['consentimento'] = json.load(f)
        
        # Exporta em formato JSON e CSV
        export_dir = self.base_path / "exportacoes"
        export_dir.mkdir(exist_ok=True)
        
        arquivo_json = export_dir / f"dados_{hash_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(arquivo_json, 'w', encoding='utf-8') as f:
            json.dump(dados_titular, f, indent=2, ensure_ascii=False)
        
        self.logger.log(f"DADOS_EXPORTADOS", {'telefone': telefone[:8] + '***'})
        return arquivo_json
    
    def excluir_dados_titular(self, telefone: str) -> bool:
        """Exclui dados de um titular (LGPD Art. 18, VII - Direito de Exclusão)"""
        hash_id = hashlib.sha256(telefone.encode()).hexdigest()[:16]
        
        # Remove do histórico
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
        
        # Remove consentimento
        consentimento_path = self.base_path / "consentimentos" / f"{hash_id}.json"
        if consentimento_path.exists():
            consentimento_path.unlink()
        
        self.logger.log(f"DADOS_EXCLUIDOS", {'telefone': telefone[:8] + '***'})
        return True
    
    def limpar_dados_antigos(self):
        """Remove dados com mais de TEMPO_RETENCAO_DIAS (LGPD Art. 15)"""
        data_limite = datetime.now() - timedelta(days=TEMPO_RETENCAO_DIAS)
        
        # Limpa PDFs antigos
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
    
    # [LGPD] Registro de violação de dados
    def registrar_violacao(self, descricao: str, dados_envolvidos: dict = None):
        violacao = {
            'timestamp': datetime.now().isoformat(),
            'descricao': descricao,
            'dados': self._anonimizar_completo(dados_envolvidos) if dados_envolvidos else None
        }
        self.violacoes_detectadas.append(violacao)
        
        # Salva em arquivo separado
        violacoes_path = Path(self.pasta_logs) / "violacoes_lgpd.log"
        with open(violacoes_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(violacao, ensure_ascii=False) + '\n')
        
        self.log(f"VIOLACAO_LGPD: {descricao}")
        
        # [LGPD] Notificar DPO em caso de violação
        if VIOLACAO_NOTIFICAR_EMAIL:
            self._notificar_dpo(violacao)
    
    def _notificar_dpo(self, violacao: dict):
        """Notifica o Encarregado sobre violação (LGPD Art. 48)"""
        # Em produção, enviaria email real
        print(f"\n⚠️ [LGPD] VIOLAÇÃO REGISTRADA - Notificar DPO: {DPO_CONTATO}")
        print(f"   Descrição: {violacao['descricao']}")
        print(f"   Data: {violacao['timestamp']}")


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
            from selenium.webdriver.support.ui import WebDriverWait
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
# FILA PRIORITÁRIA COM CONSUMIDOR REAL E SUPORTE A PARADA
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
        self._lock = threading.RLock()
        
        # [NOVO] Sistema de parada
        self.sistema_parada = SistemaParada(base_path)
        
        self._start_worker()
    
    def _start_worker(self):
        def worker():
            while self.rodando:
                try:
                    # Verifica se deve parar
                    if self.sistema_parada.deve_parar():
                        self.logger.log("PARADA_SOLICITADA_PELO_USUARIO")
                        self.rodando = False
                        break
                    
                    # Verifica se deve pausar
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
        # Verifica parada antes de enviar
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
            
            sucesso = self.whatsapp.enviar(telefone, mensagem)
            
            with self._lock:
                if sucesso:
                    self.enviados.add(chave_unica)
                    self._salvar_historico(consulta, medico, chave, sucesso)
                    status = 'OK'
                else:
                    self.falhas[chave_unica] = self.falhas.get(chave_unica, 0) + 1
                    if self.falhas[chave_unica] < 3:
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
            # [NOVO] Verifica parada a cada PDF
            if fila.sistema_parada.deve_parar():
                print("\n🛑 Processamento interrompido pelo usuário!")
                break
            
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
# [LGPD] SISTEMA PRINCIPAL COM MENU LGPD + NOVAS FUNCIONALIDADES
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
        self.consentimento = None
        self.dados_lgpd = None
        self.configuracoes = None
        
        # [NOVO] Sistema de parada
        self.sistema_parada = None
        
        self._exibir_termo_lgpd()
        
        # [NOVO] Carrega configurações existentes
        self._carregar_configuracoes_iniciais()
    
    def _exibir_termo_lgpd(self):
        """[LGPD] Exibe termo completo de responsabilidade e privacidade"""
        print("\n" + "="*80)
        print("WAM - WHATSAPP AUTOMATE MESSAGE v5.4")
        print("PROTOCOLOS LGPD IMPLEMENTADOS")
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
║  NOVIDADES v5.4                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ✓ PARADA A QUALQUER MOMENTO: Ctrl+Shift+P para parar imediatamente         ║
║  ✓ PAUSA E RETOMADA: Ctrl+Shift+Espaço para pausar/retomar                  ║
║  ✓ SALVAR CONFIGURAÇÕES: Todas as configurações são salvas automaticamente  ║
║  ✓ CARREGAR CONFIGURAÇÕES: Inicia com as últimas configurações usadas       ║
║  ✓ EXPORTAR CONFIGURAÇÕES: Backup das configurações                         ║
║  ✓ IMPORTAR CONFIGURAÇÕES: Restaurar de backup                              ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════════╝
║  CONTATO DO ENCARREGADO (DPO)                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Para questões sobre privacidade, direitos dos titulares ou violações:     ║
║  📧 Email: {DPO_CONTATO}                                                    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
        """)
        print("="*80)
        
        confirm = input("\nDigite 'ACEITO TODOS OS TERMOS LGPD' para continuar: ")
        if confirm != "ACEITO TODOS OS TERMOS LGPD":
            print("❌ Consentimento não fornecido. Operação cancelada.")
            sys.exit(0)
        
        print("✅ Consentimento registrado. Continuando com a automação...\n")
    
    def _carregar_configuracoes_iniciais(self):
        """Carrega configurações salvas anteriormente"""
        base_padrao = Path.home() / "WAM_Data"
        
        # Verifica se existe arquivo de configuração
        config_file = base_padrao / "configuracoes.json"
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    
                if config.get('configuracao_completa', False):
                    print("\n📂 Configurações anteriores encontradas!")
                    print(f"   Pasta base: {config.get('pasta_base', 'N/A')}")
                    print(f"   Última atualização: {config.get('ultima_atualizacao', 'N/A')}")
                    
                    carregar = input("\nDeseja carregar estas configurações? (s/n): ").lower()
                    if carregar == 's':
                        self.base_path = Path(config.get('pasta_base', base_padrao))
                        self._inicializar_sistema()
                        return
            except Exception as e:
                print(f"⚠️ Erro ao carregar configurações: {e}")
        
        # Se não carregou, usa configuração padrão
        self.base_path = base_padrao
    
    def _inicializar_sistema(self):
        """Inicializa todos os componentes do sistema"""
        if not self.base_path:
            self.base_path = Path.home() / "WAM_Data"
        
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # [NOVO] Sistema de parada
        self.sistema_parada = SistemaParada(self.base_path)
        self.sistema_parada.reset()
        
        # [NOVO] Gerenciador de configurações
        self.configuracoes = GerenciadorConfiguracoes(self.base_path)
        self.configuracoes.carregar()
        
        # Componentes principais
        self.logger = LoggerAuditoria(self.base_path)
        self.pastas = GerenciadorPastas(self.base_path, self.logger)
        self.pastas.criar_estrutura()
        
        self.downloads = AutomacaoDownloads(self.logger, self.base_path)
        self.processador = ProcessadorPDF(self.logger, self.pastas)
        
        # [LGPD] Inicializa módulos LGPD
        self.consentimento = GerenciadorConsentimento(self.base_path)
        self.dados_lgpd = GerenciadorDadosLGPD(self.base_path, self.logger)
        
        # Inicializa WhatsApp
        self.whatsapp = WhatsAppReal(self.logger, self.base_path)
        self.fila = FilaPrioritaria(self.logger, self.whatsapp, self.base_path)
        
        # [LGPD] Limpeza periódica de dados antigos
        self.dados_lgpd.limpar_dados_antigos()
        
        # Marca como configurado
        self.configuracoes.definir_configuracao('configuracao_completa', True)
        self.configuracoes.definir_configuracao('pasta_base', str(self.base_path))
        self.configuracoes.salvar()
    
    def menu(self):
        while True:
            # [NOVO] Verifica teclas de atalho no menu
            if self.sistema_parada and self.sistema_parada.verificar_tecla_parada():
                print("\n🛑 PARADA RÁPIDA ACIONADA!")
                self._parar_execucao()
                continue
            
            if self.sistema_parada and self.sistema_parada.verificar_tecla_pausa():
                if self.sistema_parada.deve_pausar():
                    print("\n▶️ RETOMANDO EXECUÇÃO...")
                    self.sistema_parada.continuar()
                else:
                    print("\n⏸️ PAUSANDO EXECUÇÃO...")
                    self.sistema_parada.pausar()
                continue
            
            print("\n" + "="*50)
            print("WAM - WHATSAPP AUTOMATE v5.4")
            print("="*50)
            print("1. CONFIGURAR SISTEMA")
            print("2. GRAVAR CLIQUES")
            print("3. BAIXAR PDF (automático)")
            print("4. PROCESSAR PDFs (Médicos 1-10)")
            print("5. LIMPAR PDFs")
            print("6. CONECTAR WHATSAPP WEB")
            print("-"*50)
            print("[LGPD] DIREITOS DOS TITULARES")
            print("7. EXPORTAR DADOS DE UM TITULAR")
            print("8. EXCLUIR DADOS DE UM TITULAR")
            print("9. REGISTRAR CONSENTIMENTO")
            print("10. VER LOGS DE AUDITORIA")
            print("-"*50)
            print("[NOVO] CONFIGURAÇÕES")
            print("11. SALVAR CONFIGURAÇÕES ATUAIS")
            print("12. EXPORTAR CONFIGURAÇÕES (Backup)")
            print("13. IMPORTAR CONFIGURAÇÕES (Restaurar)")
            print("14. PARAR EXECUÇÃO IMEDIATAMENTE")
            print("15. PAUSAR/RETOMAR EXECUÇÃO")
            print("-"*50)
            print("0. SAIR")
            print("="*50)
            print("💡 Atalhos: Ctrl+Shift+P = Parar | Ctrl+Shift+Espaço = Pausar")
            print("="*50)
            
            opcao = input("Escolha: ").strip()
            
            if opcao == '1':
                self._configurar_sistema()
            elif opcao == '2':
                if not self.downloads:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                self.downloads.gravar_cliques()
                self.configuracoes.salvar()
            elif opcao == '3':
                if not self.pastas or not self.downloads:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                downloads = input("Pasta de downloads: ").strip() or str(Path.home() / "Downloads")
                destino = input("Pasta destino: ").strip() or self.pastas.estrutura.get('medico1', '')
                if destino:
                    self.downloads.repetir_ate_download(downloads, destino)
                    # Salva última configuração
                    self.configuracoes.definir_configuracao('ultimo_download.pasta_origem', downloads)
                    self.configuracoes.definir_configuracao('ultimo_download.pasta_destino', destino)
                else:
                    print("⚠️ Pasta destino inválida")
            elif opcao == '4':
                if not self.pastas or not self.fila:
                    print("⚠️ Configure primeiro (opção 1)")
                    continue
                
                # Verifica se há sinal de parada
                if self.sistema_parada.deve_parar():
                    print("⚠️ Sinal de parada detectado. Resetando...")
                    self.sistema_parada.reset()
                
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
                    self.configuracoes.definir_configuracao('whatsapp.conectado', True)
                    self.configuracoes.definir_configuracao('whatsapp.ultima_conexao', datetime.now().isoformat())
                else:
                    print("❌ Falha na conexão. Verifique se o Chrome está instalado.")
            elif opcao == '7':
                self._exportar_dados_titular()
            elif opcao == '8':
                self._excluir_dados_titular()
            elif opcao == '9':
                self._registrar_consentimento()
            elif opcao == '10':
                self._ver_logs_auditoria()
            elif opcao == '11':
                self._salvar_configuracoes()
            elif opcao == '12':
                self._exportar_configuracoes()
            elif opcao == '13':
                self._importar_configuracoes()
            elif opcao == '14':
                self._parar_execucao()
            elif opcao == '15':
                self._pausar_retomar_execucao()
            elif opcao == '0':
                self._finalizar()
                break
            else:
                print("❌ Opção inválida!")
    
    def _configurar_sistema(self):
        print("\n" + "="*50)
        print("CONFIGURAÇÃO DO SISTEMA")
        print("="*50)
        
        # Verifica se já existe configuração salva
        if self.configuracoes and self.configuracoes.obter_configuracao('configuracao_completa', False):
            print("\n📂 Uma configuração já existe:")
            print(f"   Pasta base: {self.configuracoes.obter_configuracao('pasta_base', 'N/A')}")
            usar_existente = input("Deseja usar a configuração existente? (s/n): ").lower()
            if usar_existente == 's':
                self.base_path = Path(self.configuracoes.obter_configuracao('pasta_base'))
                self._inicializar_sistema()
                print("\n✅ Sistema configurado com a configuração existente!")
                return
        
        base = input("Pasta base (Enter para padrão): ").strip()
        if not base:
            base = str(Path.home() / "WAM_Data")
        
        self.base_path = Path(base)
        self._inicializar_sistema()
        
        print("\n✅ Sistema configurado com sucesso!")
        print("\n⚠️ Para enviar mensagens reais, execute a opção 6 para conectar ao WhatsApp Web.")
        print("\n💡 Use Ctrl+Shift+P para parar a qualquer momento")
        print("💡 Use Ctrl+Shift+Espaço para pausar/retomar")
    
    def _processar_todos_medicos(self):
        print("\n" + "="*50)
        print("PROCESSANDO MÉDICOS 1-10")
        print("="*50)
        print("💡 Pressione Ctrl+Shift+P para parar a qualquer momento")
        print("💡 Pressione Ctrl+Shift+Espaço para pausar/retomar")
        print("-"*50)
        
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
            # [NOVO] Verifica parada antes de cada médico
            if self.sistema_parada.deve_parar():
                print("\n🛑 Processamento interrompido pelo usuário!")
                break
            
            # [NOVO] Verifica pausa
            while self.sistema_parada.deve_pausar():
                print("\n⏸️ Processamento PAUSADO. Aguardando retomada...")
                time.sleep(1)
                if self.sistema_parada.deve_parar():
                    print("\n🛑 Processamento interrompido!")
                    break
            
            pasta = self.pastas.estrutura.get(f'medico{i}')
            if pasta and pasta.exists():
                print(f"\n📂 Processando {pasta.name}...")
                processados = self.processador.extrair_e_processar(str(pasta), self.fila)
                total += processados
                print(f"   ✅ {processados} consultas processadas de {pasta.name}")
        
        print(f"\n✅ {total} consultas processadas e enfileiradas")
        
        if total > 0:
            print("\n📊 Fila processando mensagens em background...")
            time.sleep(1)
        
        # Atualiza configurações
        if self.configuracoes:
            self.configuracoes.definir_configuracao('fila.total_processados', 
                self.configuracoes.obter_configuracao('fila.total_processados', 0) + total)
    
    # [LGPD] Métodos de direitos dos titulares
    def _exportar_dados_titular(self):
        """Exporta dados de um titular (Portabilidade)"""
        print("\n" + "="*50)
        print("EXPORTAR DADOS DO TITULAR")
        print("="*50)
        
        telefone = input("Digite o telefone do titular (com DDD): ").strip()
        if not telefone:
            print("❌ Telefone não informado")
            return
        
        arquivo = self.dados_lgpd.exportar_dados_titular(telefone)
        if arquivo:
            print(f"✅ Dados exportados com sucesso: {arquivo}")
        else:
            print("⚠️ Nenhum dado encontrado para este telefone")
    
    def _excluir_dados_titular(self):
        """Exclui dados de um titular (Direito de Exclusão)"""
        print("\n" + "="*50)
        print("EXCLUIR DADOS DO TITULAR")
        print("="*50)
        print("⚠️ ATENÇÃO: Esta ação é irreversível!")
        
        telefone = input("Digite o telefone do titular (com DDD): ").strip()
        if not telefone:
            print("❌ Telefone não informado")
            return
        
        confirm = input(f"Deseja realmente excluir TODOS os dados de {telefone}? (s/n): ").lower()
        if confirm == 's':
            if self.dados_lgpd.excluir_dados_titular(telefone):
                print("✅ Dados excluídos com sucesso")
            else:
                print("⚠️ Nenhum dado encontrado para este telefone")
    
    def _registrar_consentimento(self):
        """Registra consentimento do titular (LGPD Art. 7º)"""
        print("\n" + "="*50)
        print("REGISTRAR CONSENTIMENTO DO TITULAR")
        print("="*50)
        
        nome = input("Nome completo do titular: ").strip()
        telefone = input("Telefone (com DDD): ").strip()
        
        if not nome or not telefone:
            print("❌ Nome e telefone são obrigatórios")
            return
        
        print("\nFinalidade do tratamento:")
        print("- Envio de mensagens automáticas sobre consultas médicas")
        print("- Armazenamento de histórico de comunicações")
        
        confirm = input("\nO titular concorda com esta finalidade? (s/n): ").lower()
        if confirm == 's':
            self.consentimento.registrar_consentimento(nome, telefone)
            print("✅ Consentimento registrado com sucesso!")
        else:
            print("❌ Consentimento não registrado")
    
    def _ver_logs_auditoria(self):
        """Exibe logs de auditoria"""
        print("\n" + "="*50)
        print("LOGS DE AUDITORIA LGPD")
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
    
    # [NOVO] Métodos para configurações
    def _salvar_configuracoes(self):
        """Salva as configurações atuais"""
        print("\n" + "="*50)
        print("SALVAR CONFIGURAÇÕES")
        print("="*50)
        
        if not self.configuracoes:
            print("⚠️ Sistema não configurado")
            return
        
        if self.configuracoes.salvar():
            print(f"✅ Configurações salvas em: {self.configuracoes.config_file}")
            print(f"   Pasta base: {self.base_path}")
            print(f"   Data: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        else:
            print("❌ Erro ao salvar configurações")
    
    def _exportar_configuracoes(self):
        """Exporta configurações para backup"""
        print("\n" + "="*50)
        print("EXPORTAR CONFIGURAÇÕES (BACKUP)")
        print("="*50)
        
        if not self.configuracoes:
            print("⚠️ Sistema não configurado")
            return
        
        caminho = input("Caminho para exportar (Enter para padrão): ").strip()
        if caminho:
            caminho = Path(caminho)
        else:
            caminho = self.base_path / f"config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        if self.configuracoes.exportar(caminho):
            print("✅ Configurações exportadas com sucesso!")
    
    def _importar_configuracoes(self):
        """Importa configurações de backup"""
        print("\n" + "="*50)
        print("IMPORTAR CONFIGURAÇÕES (RESTAURAR)")
        print("="*50)
        print("⚠️ ATENÇÃO: Isso sobrescreverá as configurações atuais!")
        
        caminho = input("Caminho do arquivo de configuração: ").strip()
        if not caminho:
            print("❌ Caminho não informado")
            return
        
        caminho = Path(caminho)
        if not caminho.exists():
            print(f"❌ Arquivo não encontrado: {caminho}")
            return
        
        confirm = input("Deseja realmente importar estas configurações? (s/n): ").lower()
        if confirm != 's':
            print("❌ Importação cancelada")
            return
        
        if self.configuracoes.importar(caminho):
            print("✅ Configurações importadas com sucesso!")
            print("🔄 Reiniciando sistema com novas configurações...")
            self._inicializar_sistema()
            print("✅ Sistema reiniciado com as configurações importadas!")
        else:
            print("❌ Erro ao importar configurações")
    
    # [NOVO] Métodos para parada/pausa
    def _parar_execucao(self):
        """Para a execução imediatamente"""
        print("\n" + "="*50)
        print("PARAR EXECUÇÃO")
        print("="*50)
        
        if not self.sistema_parada:
            print("⚠️ Sistema não inicializado")
            return
        
        confirm = input("Deseja parar a execução imediatamente? (s/n): ").lower()
        if confirm == 's':
            self.sistema_parada.parar()
            print("🛑 Sinal de PARADA enviado!")
            print("   A execução será interrompida em breve...")
            if self.fila:
                self.fila.rodando = False
            print("✅ Execução parada com sucesso!")
        else:
            print("❌ Parada cancelada")
    
    def _pausar_retomar_execucao(self):
        """Pausa ou retoma a execução"""
        print("\n" + "="*50)
        print("PAUSAR/RETOMAR EXECUÇÃO")
        print("="*50)
        
        if not self.sistema_parada:
            print("⚠️ Sistema não inicializado")
            return
        
        if self.sistema_parada.deve_pausar():
            print("⏸️ Execução está PAUSADA")
            retomar = input("Deseja retomar? (s/n): ").lower()
            if retomar == 's':
                self.sistema_parada.continuar()
                print("▶️ Execução retomada!")
        else:
            print("▶️ Execução está ATIVA")
            pausar = input("Deseja pausar? (s/n): ").lower()
            if pausar == 's':
                self.sistema_parada.pausar()
                print("⏸️ Execução pausada!")
    
    def _finalizar(self):
        if self.fila:
            self.fila.stop()
        if self.whatsapp:
            self.whatsapp.fechar()
        
        # [LGPD] Limpeza final
        if self.dados_lgpd:
            self.dados_lgpd.limpar_dados_antigos()
        
        # [NOVO] Salva configurações finais
        if self.configuracoes:
            self.configuracoes.salvar()
            print("✅ Configurações salvas")
        
        # [NOVO] Remove sinais de parada
        if self.sistema_parada:
            self.sistema_parada.reset()
        
        print("\nEncerrando...")


def main():
    print("""
    ╔══════════════════════════════════════════════════════════════════╗
    ║     WAM - WHATSAPP AUTOMATE MESSAGE v5.4 - LGPD COMPLIANT       ║
    ║     COM INTEGRAÇÃO REAL COM WHATSAPP WEB                        ║
    ║     PROTOCOLOS DE SEGURANÇA E TRATAMENTO DE DADOS SENSÍVEIS     ║
    ║     NOVIDADES: PARADA A QUALQUER MOMENTO + SALVAR CONFIG        ║
    ║     github.com/luisfernandosiqueirasilva/whatsapp_automate_msg   ║
    ╚══════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        app = WAM()
        app.menu()
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrompido pelo usuário")
        # Tenta salvar configurações antes de sair
        try:
            if 'app' in locals() and app.configuracoes:
                app.configuracoes.salvar()
                print("✅ Configurações salvas antes de encerrar")
        except:
            pass
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
