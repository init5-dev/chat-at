import sys
import time
import copy
import re
import os
import json
import openai
from threading import Thread
from datetime import datetime
import secret
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
import qdarktheme
from atengine.atchat import AtChat

apikey_file = "./api.key"

class Sumarize(QThread):
	summary = pyqtSignal(str)
	error = pyqtSignal(Exception)

	def __init__(self, parent):
		super(Sumarize, self).__init__(parent)
		self.parent = parent

	#@pyqtSlot(str)
	def run(self):
		while self.parent.isVisible():
			chat = self.parent.chatBox.toPlainText()
			limit = 150 if len(chat) > 150 else len(chat)
			chatStart = chat[0:limit]
			command = '''
	Sigue estrictamente mis instrucciones. Resume el tema del siguiente fragmento de conversación en una frase breve:

	"%s".

	Quiero que tu respuesta tenga estrictamente el siguiente formato: "#TEMA: tema".
			''' % chatStart
			atc = AtChat(self.parent.apikey)
			atc.temperature = 0
			atc.topP = 0
			atc.frequencyPenalty = 0
			atc.presencePenalty = 0

			try:
				answer = atc.answer(command)
			except Exception as e:
				self.error.emit(e)
				self.summary.emit('')
				return

			answer = answer.split(':')[1].strip()
			answer = re.sub(r"\.$", "", answer) 
			self.summary.emit(answer)
			#print(f'Sumario creado: {answer}.')
			time.sleep(10)


class ChatGPT(QWidget):

	def __init__(self, parent=None):
		super(ChatGPT, self).__init__(parent)

		self.mistery = 'ep-k9CZ0JPRWKgiz1xil0jZNkls5SIuR87XgNN6ZuN4=' #clave para guardar y leer la API key de OpenAI
		self.apikey = ''

		self.configureWindow()
		self.createLayout()
		self.createMenuBar() #desactivado hasta que implemente las funciones
		self.createChatBox()
		self.createInputBox()
		self.createSendButton()	
		self.createCancelButton()

		self.inputBox.setFocus()
		self.keyPressEvent = self.shortcut

		self.chatBox.insertHtml('<b style="color:#3EB489">[%s] AT:</b> ¡Hola!<br>' % self.currTime())

	def resizeEvent(self, e):
		self.createAttributes()
	
	def showEvent(self, e):
		self.startSummarizer()

	def configureWindow(self):
		self.setWindowTitle('¡Chat AT!')
		self.setWindowIcon(QIcon('muelagpt.png'))

	def createAttributes(self):
		self.apikey = self.getAPIKey()
		self.chatbot = AtChat(self.apikey)
		self.loadModel()
		self.answer = ''
		self.dots = -1
		self.cancelled = False
		self.answerThread = Thread()
		self.summary = 'Saludo del chatbot.'

	def createLayout(self):
		self.layout = QGridLayout()
		self.setLayout(self.layout)

	def createMenuBar(self):
		self.menuBar = QMenuBar()
		self.fileMenu = self.menuBar.addMenu('Archivo')
		self.confMenu = self.menuBar.addMenu('Configuración')
		self.helpMenu = self.menuBar.addMenu('Ayuda')

		openAction = QAction(QIcon(), 'Abrir', self)
		openAction.triggered.connect(self.openChat)

		saveAction = QAction(QIcon(), 'Guardar', self)
		saveAction.triggered.connect(self.saveChat)

		apiAction = QAction(QIcon(), 'Clave de la API', self)
		apiAction.triggered.connect(self.setAPIkey)
		
		gpt4Action = QAction(QIcon(), 'Usar GPT-4', self, checkable = True)
		gpt4Action.triggered.connect(self.useGpt4)

		if self.loadConf()['model'] == 'gpt-4':
			gpt4Action.setChecked(True)

		aboutAction = QAction(QIcon(), 'Acerca de...', self)
		aboutAction.triggered.connect(self.about)

		self.fileMenu.addAction(openAction)
		self.fileMenu.addAction(saveAction)
		self.confMenu.addAction(apiAction)
		self.confMenu.addAction(gpt4Action)	
		self.helpMenu.addAction(aboutAction)

		self.layout.addWidget(self.menuBar, 0, 0, 1, 5)

	def createChatBox(self):
		self.chatBox = QTextEdit()
		self.chatBox.setReadOnly(True)
		#self.chatBox.setStyleSheet('QTextEdit:disabled {background-color:white;color:black}')
		#self.chatBox.cursorPositionChanged.connect(self.moveCursorToEnd)
		self.layout.addWidget(self.chatBox, 1, 0, 1, 10)

	def createInputBox(self):
		self.inputBox = QPlainTextEdit()
		self.inputBox.setMaximumSize(QSize(10000, 50))
		self.inputBox.cursorPositionChanged.connect(self.setButtonState)
		#self.keyPressEvent = self.checkForSend
		self.layout.addWidget(self.inputBox, 2, 0, 2, 9)

	def createSendButton(self):
		self.sendButton = QPushButton()
		self.sendButton.setText('Enviar')
		self.sendButton.setEnabled(False)
		self.sendButton.clicked.connect(self.prompt)
		self.layout.addWidget(self.sendButton, 2, 9, 1, 1)

	def createCancelButton(self):
		self.cancelButton = QPushButton()
		self.cancelButton.setText('Cancelar')
		self.cancelButton.setEnabled(False)
		self.cancelButton.clicked.connect(self.cancel)
		self.layout.addWidget(self.cancelButton, 3, 9, 1, 1)

	def startSummarizer(self):
		self.sumarizer = Sumarize(self)
		self.sumarizer.summary[str].connect(self.setSummary)
		self.sumarizer.error[Exception].connect(lambda: self.setSummary('Chat sin nombre'))
		self.sumarizer.start()

	def setSummary(self, summary):
		if len(summary):
			self.summary = summary

	def resetChatbot(self):
		cloneChatbot = copy.deepcopy(self.chatbot)
		self.chatbot = cloneChatbot

	def shortcut(self, e):
		content = self.inputBox.toPlainText().strip()
		if e.key() == Qt.Key_Escape and self.answerThread.is_alive():
			self.cancel()
		elif e.key() == Qt.Key_Insert and len(content):
			self.prompt()

	def setButtonState(self):
		content = self.inputBox.toPlainText().strip()

		if not len(content):
			self.sendButton.setEnabled(False)
		else:
			self.sendButton.setEnabled(True)

	def moveCursorToEnd(self, e=None):
		self.chatBox.moveCursor(QTextCursor.End)

	def loadConf(self):
		with open('conf.json', 'r') as f:
			return json.load(f)

	def loadModel(self):
		data = self.loadConf()
		self.chatbot.model = data['model']
		print('Ejecutando chat con: %s' % data['model'])

	def setModel(self, model):
		data = self.loadConf()
		data['model'] = model
		with open('conf.json', 'w') as f:
			json.dump(data, f)
		self.chatbot.model = model

	def useGpt4(self):
		self.setModel('gpt-4')
		print('Ejecutando chat con: %s' % self.chatbot.model)

	def openChat(self):
		
		file_path = QFileDialog.getOpenFileName(self,'Abrir Archivo','chats','Chat Files (*.chat)')[0]
    
		if file_path:
			with open(file_path, 'r') as f:
				data = json.load(f)
				self.chatBox.setHtml(data['text'])

	def saveChat(self):

		filename = os.path.join('chats', self.summary)
		file_path = QFileDialog.getSaveFileName(self,'Guardar Archivo', filename,'Chat Files (*.chat)')[0]
    	
		if file_path:
			print(file_path)
			data = {"text" : self.chatBox.toHtml()}
			if file_path.rfind('.chat') == -1:
				file_path = file_path + '.chat'
			print(file_path)

			with open(file_path,'w') as f:
				json.dump(data,f)

	def about(self):
		QMessageBox.information(self, 
			'Acerca de...', 
			'''<p style="text-align:center">
					Nelson Ochagavía &#127279; 2023</p>'''
  )

	def setAPIkey(self):
		apikey, ok = QInputDialog.getText(self, 'Clave de la API', 'Escribe o pega tu clave de la API de OpenAI.')

		if ok:
			print(apikey)

			if not len(apikey.strip()):
				QMessageBox.critical(self, 'Error', '¡Introduce la clave!')
				return self.setAPIkey()

			secret.write_file(self.mistery, apikey_file, apikey.strip())
			self.apikey = self.getAPIKey()
			self.chatbot.setAPIKey(self.apikey)

			if self.testAPIKey():
				QMessageBox.information(self, 'Clave de la API', '¡La clave fue instalada correctamente!')
			else:
				QMessageBox.critical(self, 'Clave de la API','Lo siento, la clave es incorrecta.')			
		else:
			if not len(apikey.strip()):
				QMessageBox.warning(self, 'Advertencia', 'Si no introduces tu clave de la API de Open AI, ¡no puedes usar el chat!')

	def getAPIKey(self, firstUse=True):
		try:
			return secret.read_file(self.mistery, apikey_file)
		except:
			if not os.path.exists(apikey_file):
				self.setAPIkey()
			else:
				QMessageBox.critical(self, 'Clave de la API', 'Problema al leer la clave de la API. Contacta con el desarrollador.')
			return ''
		
	def testAPIKey(self):
		try:
			openai.Completion.create(
					engine = 'ada',
					prompt = 'Hola ',
					temperature = 0,
					top_p = 0,
				)
		except AuthenticationError as e:
			return False

		return True

	def chat(self, prompt):
		self.moveCursorToEnd()

		try:
			self.answer = self.chatbot.answer(prompt)
		except Exception as e:
			self.errorActions(e)

	def cancel(self):
		self.cancelled = True
		self.answerThread = Thread()
		self.resetChatbot()
		self.removeGptLine()
		self.answer = ''
		self.cancelButton.setEnabled(True)
		self.chatBox.ensureCursorVisible()
		self.inputBox.setReadOnly(False)
		self.chatBox.setEnabled(True)
		self.inputBox.setFocus()

	def stopByError(self):
		self.cancelled = True
		self.answerThread = Thread()
		self.resetChatbot()
		self.errorActions()
		self.answer = ''
		self.cancelButton.setEnabled(True)
		self.chatBox.ensureCursorVisible()
		self.inputBox.setReadOnly(False)
		self.chatBox.setEnabled(True)
		self.inputBox.setFocus()

	def errorActions(self, e):
		cursor = self.chatBox.textCursor()
		cursor.movePosition(QTextCursor.Down)
		cursor.select(QTextCursor.LineUnderCursor)
		cursor.removeSelectedText()
		cursor = self.chatBox.textCursor()
		cursor.movePosition(QTextCursor.Down)
		cursor.select(QTextCursor.LineUnderCursor)
		cursor.removeSelectedText()

		msg = 'Error inesperado'

		if type(e) == openai.error.APIError:
			msg = "Error de OpenAI. Espera unos minutos e inténtalo de nuevo. Si el problema persiste, contacta con la empresa."
		elif type(e) == openai.error.Timeout:
			msg = "Tiempo de espera agotado. Espera unos minutos e inténtalo de nuevo. Si el problema persiste, contacta con la empresa."
		elif type(e) == openai.error.RateLimitError:
			msg = "Por favor, asegúrate de que tienes conexión a Internet."
		elif type(e) == openai.error.InvalidRequestError:
			msg = "¡Atwood falló! Hay algo mal en el código. Por favor, contacta con el desarrollador usando este email: nelson.ochagavia@gmail.com. Enviale este texto:\n ERROR: openai.error.InvalidRequestError\nARGS = %s\nKWARGS = %s" % (args, kwargs)
		elif type(e) == openai.error.AuthenticationError:	
			msg = "API key incorrecta. Busca tu API key en https://platform.openai.com/account/api-keys y regístrala aquí en Atwood."
		elif type(e) == openai.error.ServiceUnavailableError:
			msg = "¡El servidor de OpenAI sigue sobrecargado! Inténtalo más tarde. Y, si estás usando la prueba gratuita de GPT, es buena idea adquirir un plan de pago."
		else:
			msg = e
			print(type(e))
		
		self.chatBox.insertHtml(' <i style="color:orange">[%s] <b>AT:</b> %s</i><br>' % (self.currTime(), msg))

	def writeAnswer(self):
		answer = self.answer.replace('<br>', '\n').replace('&nbsp', ' ').replace('```', '') + '\n'
		self.chatBox.insertPlainText(answer)	

	def checkIfDone(self):
		if self.answerThread.is_alive():
			if not self.cancelled:
				self.waitingMessage()
				QTimer.singleShot(100, self.checkIfDone)
		else:
			if not self.cancelled:
				self.removeDots()
				self.writeAnswer()
				self.chatBox.ensureCursorVisible()
				self.answer = ''
				self.inputBox.setReadOnly(False)
				self.chatBox.setEnabled(True)
				self.cancelButton.setEnabled(True)
				self.inputBox.setFocus()

	def removeDots(self):
		cursor = self.chatBox.textCursor()
		cursor.movePosition(QTextCursor.Down)
		cursor.select(QTextCursor.LineUnderCursor)
		cursor.removeSelectedText()
		cursor.insertHtml('<b style="color:#3EB489">[%s] AT</b>: ' % self.currTime())

	def removeGptLine(self):
		cursor = self.chatBox.textCursor()
		cursor.movePosition(QTextCursor.Down)
		cursor.select(QTextCursor.LineUnderCursor)
		cursor.removeSelectedText()
		#cursor.insertHtml('<b>Yo</b>: ')
		cursor = self.chatBox.textCursor() 
		cursor.movePosition(QTextCursor.Down)
		cursor.select(QTextCursor.LineUnderCursor)
		cursor.removeSelectedText()
		self.chatBox.insertHtml('<i style="color:gray">[%s] Respuesta cancelada</i><br>' % self.currTime())

	def waitingMessage(self):

		self.removeDots()
		message = '<i>%s</i>' % '.' * self.dots
		
		if self.dots >= 3:
			self.dots = -1	

		self.chatBox.insertHtml(message)
		self.chatBox.ensureCursorVisible()
		self.dots = self.dots + 1

	def currTime(self):
		now = datetime.now()
		return now.strftime("%H:%M:%S")

	def prompt(self):
		self.cancelled = False
		prompt = self.inputBox.toPlainText().strip()
		#prompt = prompt.replace('\n', '<br>')
		self.inputBox.clear()
		self.moveCursorToEnd()
		self.chatBox.insertHtml('<strong style="color:#3EB489">[%s] Yo:</strong> ' % self.currTime())
		self.chatBox.insertPlainText(prompt)
		self.chatBox.insertHtml('<br><b style="color:#3EB489">[%s] AT:</b>' % self.currTime())
		self.chatBox.ensureCursorVisible()
		self.inputBox.setReadOnly(True)
		self.chatBox.setEnabled(False)
		self.cancelButton.setEnabled(True)
		self.moveCursorToEnd()
	
		self.answerThread = Thread(target=self.chat, args=[prompt])
		self.answerThread.start()
		QTimer.singleShot(100, self.checkIfDone)
		

if __name__ == '__main__':
	app = QApplication(sys.argv)
	qdarktheme.setup_theme()
	geometry = app.desktop().screenGeometry()
	chatGPT = ChatGPT()
	chatGPT.resize(geometry.width(), geometry.height())
	chatGPT.show()
	sys.exit(app.exec_())
		