#!/usr/bin/env python
from xml.etree import ElementTree
from timecode import Timecode 
#libreria externa descargada
#import operator
from PySide.QtCore import *
from PySide.QtGui import *
import pytimecode as pytc
import sys
import os
import copy
#subprocess for parse system calls like rvio command
import subprocess

# Adds Toolkit to the PYTHONPATH so we can use the authentication framework.
#Make sure Shotgun desktp app is installed
sys.path.insert(0, "/Applications/Shotgun.app/Contents/Resources/Python/tk-framework-desktopstartup/python/tk-core/python")
# Imports the authenticator class.
from tank_vendor.shotgun_authentication import ShotgunAuthenticator

class XMLMainWindow(QMainWindow):
    def __init__(self):
        super(XMLMainWindow, self).__init__()
        self.setGeometry(0, 0, 1600, 800)
        
        self.header = ['Shot Code', 'Sequence', 'Cut Order', 'Source TC in', 'Source TC out',\
            'Record TC in', 'Record TC out', \
            'Cut In', 'Cut Out', 'Cut Duration', 'pathurl']
        #only clip item events --> shot list
        self.shot_list = [] 
        
        #info about sequence such as name fps
        self.sequence_info = {}
        self.selected_project = {}
 
        #menu bars, status bar, titles
        self.openAction = QAction('Open XML', self)
        self.openAction.setStatusTip('Open XML')
        self.openAction.triggered.connect(self.open_xml)
        
        self.quitAction = QAction('Close', self)
        self.quitAction.setStatusTip('Exit application')
        self.quitAction.triggered.connect(self.close)

        self.sgAction = QAction('Shotgun select project', self)
        self.sgAction.setStatusTip('Auth in shotgun and select project')
        self.sgAction.triggered.connect(selection_functions)

        self.sgshotsAction = QAction('Shotgun create shots', self)
        self.sgshotsAction.setStatusTip('Create shots related with table events')
        self.sgshotsAction.triggered.connect(create_shotgun_shots)
        
        self.sgversionsAction = QAction('Shotgun create versions for shots', self)
        self.sgversionsAction.setStatusTip('Create versions related with table events')
        self.sgversionsAction.triggered.connect(create_shotgun_versions)

        self.menubar = self.menuBar()
        self.fileMenu = self.menubar.addMenu('File')
        self.shotgunMenu = self.menubar.addMenu('Shotgun Connect')
        
        
        self.fileMenu.addAction(self.openAction)
        self.fileMenu.addAction(self.quitAction)
        
        self.shotgunMenu.addAction(self.sgAction)
        self.shotgunMenu.addAction(self.sgshotsAction)
        self.shotgunMenu.addAction(self.sgversionsAction)

        self.openAction.setEnabled(False)
        self.sgshotsAction.setEnabled(False)
        self.sgversionsAction.setEnabled(False)

        self.statusBar()
    
    def populate_table(self):
        #add the xml table
        self.table = XMLTableView(self, self.shot_list, self.header, self.sequence_info)
        self.setCentralWidget(self.table)

    def open_xml(self):
    	self.xmlFile, _ = QFileDialog.getOpenFileName(self, "Open XML file from Resolve", QFSFileEngine.homePath(), "xml files(*.xml)")
        self.xml_paser()
        self.setWindowTitle("xml2shots   ////    " + self.xmlFile + "     ////  FPS:" + str(self.sequence_info['sec_framerate']))
        self.populate_table()
        self.sgshotsAction.setEnabled(True)

    def xml_paser(self):
		with open(self.xmlFile, 'rt') as f:
		    tree = ElementTree.parse(f)
		root = tree.getroot()

		#complete event list with tansition events, clip events and several tracks
		event_list = []
		
		for sequence_item in root.findall("./sequence"):
			sec_name = sequence_item.find('name').text.split(" (")[0]
			sec_framerate = int(sequence_item.find('./timecode/rate/timebase').text)
			sec_cut_in = int(sequence_item.find('./timecode/frame').text)
			sec_tc_in = Timecode(sec_framerate, sequence_item.find('./timecode/string').text)
			sec_tc_duration = Timecode(sec_framerate,)
			sec_tc_duration.frames = int(sequence_item.find('./duration').text)
			sec_tc_out = sec_tc_in + sec_tc_duration
		self.sequence_info = {"sec_name":sec_name,"sec_framerate":sec_framerate,\
		"sec_cut_duration":sec_tc_duration.frames,"sec_tc_in":sec_tc_in,"sec_tc_out":sec_tc_out,\
		"sec_cut_in":sec_cut_in,"sec_cut_out":sec_tc_out.frame_number}
		#print sequence_info

		video_tree = root.find('sequence/media/video')
		for child in video_tree.iter():
			if child.tag == 'clipitem':
				#print "------------------------"
				#print child.tag
				clip_occurence = child.attrib['id'].split()[-1]
				#print "id: ", clip_occurence
				clip_item = {"type":child.tag}
				for element in child:
					if element.tag in ('name', 'duration', 'start', 'end', 'in', 'out'):
						clip_item.update({element.tag:element.text})
					if element.tag == "file":
						if clip_occurence == "0":
							#print "SOURCE CLIP NUEVO"
							for field in element.iter():
								if field.tag == 'pathurl':
									file_path = field.text.split("//")[1]
									clip_item.update({field.tag:file_path})
								elif field.tag == 'timecode':
										for subfield in field.iter():
											if subfield.tag == "string":
												clip_item.update({"clip_tc_in":subfield.text})
												
						else:
							#print "SOURCE CLIP EXISTENTE"
							for event_list_item in event_list:
								if clip_item['name'] in event_list_item.values():
									clip_item.update({"pathurl":event_list_item["pathurl"]})
									clip_item.update({"clip_tc_in":event_list_item["clip_tc_in"]})
						clip_in = Timecode(sec_framerate,)
						clip_in.frames = int(clip_item['in'])
						shot_tc_source_in = Timecode(sec_framerate,clip_item['clip_tc_in']) + clip_in
						clip_out = Timecode(sec_framerate,)
						clip_out.frames = int(clip_item['out'])
						shot_tc_source_out = Timecode(sec_framerate,clip_item['clip_tc_in']) + clip_out
						
						clip_item.update({"shot_tc_source_in": str(shot_tc_source_in)})
						clip_item.update({"shot_tc_source_out": str(shot_tc_source_out)})
						###zero based frame numbers
						clip_item.update({"shot_cut_source_in": str(shot_tc_source_in.frame_number)})
						clip_item.update({"shot_cut_source_out": str(shot_tc_source_out.frame_number)})
						clip_item.update({"cut_duration": int(clip_item['out'])-int(clip_item['in'])})
				#print clip_item
				event_list.append(clip_item)
			elif child.tag == 'transitionitem':
				#print "------------------------"
				#print child.tag
				clip_item = {"type":child.tag}
				for element in child.iter():
					if element.tag in ("start", "end", "name"):
						clip_item.update({element.tag:element.text})
				event_list.append(clip_item)
		###seek for transitioned start or end clips and update record tc			
		for event_list_item in event_list:
			if event_list_item['type'] == 'clipitem':
				if event_list_item['start'] == "-1":
					clip_item_index = event_list.index(event_list_item)
					transition_data = event_list[clip_item_index-1]
					event_list_item['start']=transition_data['start']		
				tc_start=Timecode(sec_framerate,)
				tc_start.frames=int(event_list_item['start'])
				event_list_item.update({'record_tc_in':self.sequence_info['sec_tc_in']+tc_start})	
				if event_list_item['end'] == "-1":
					clip_item_index = event_list.index(event_list_item)
					transition_data = event_list[clip_item_index+1]
					event_list_item['end']=transition_data['end']
				tc_end=Timecode(sec_framerate,)
				tc_end.frames=int(event_list_item['end'])
				event_list_item.update({'record_tc_out':self.sequence_info['sec_tc_in']+tc_end})
				self.shot_list.append(event_list_item)
		#order shot list by start frame on record (record cut in)
		self.shot_list = sorted(self.shot_list, key=lambda k: int(k['start']))
		for idx, shot_list_item in enumerate(self.shot_list):
		#cut order is index with 3d padding begining in 1 multiple of 10 for interpolate new posible shots manually
			shot_list_item.update({"cut_order": "{0:03d}".format((idx+1)*10)})
			shot_list_item.update({"shot_code": "PL_" + str(shot_list_item["cut_order"]) + "_" + self.sequence_info['sec_name']})



class XMLTableView(QWidget):
    def __init__(self, parent, data_list, header, sequence_info):        
        super(XMLTableView, self).__init__(parent)
        #self.setGeometry(300, 200, 570, 450)
        self.table_view = QTableWidget(parent=self)
        self.table_view.setRowCount(len(data_list))
        self.table_view.setColumnCount(len(header))
        self.header = header
        layout = QGridLayout()
        layout.addWidget(self.table_view)
        self.setLayout(layout)
        self.set_my_data(data_list, sequence_info)        
        self.clip = QApplication.clipboard()
        self.table_view.resizeColumnsToContents()
    
    def set_my_data(self,data_list,sequence_info):
        self.data = data_list
        self.table_view.setHorizontalHeaderLabels(self.header)
        n = 0
        for list_item in self.data:
            newitem = QTableWidgetItem(str(list_item['shot_code']))
            self.table_view.setItem(n, 0, newitem)
            newitem = QTableWidgetItem(str(sequence_info['sec_name']))
            self.table_view.setItem(n, 1, newitem)
            newitem = QTableWidgetItem(str(list_item['cut_order']))
            self.table_view.setItem(n, 2, newitem)
            newitem = QTableWidgetItem(str(list_item['shot_tc_source_in']))
            self.table_view.setItem(n, 3, newitem)
            newitem = QTableWidgetItem(str(list_item['shot_tc_source_out']))
            self.table_view.setItem(n, 4, newitem)
            newitem = QTableWidgetItem(str(list_item['record_tc_in']))
            self.table_view.setItem(n, 5, newitem)
            newitem = QTableWidgetItem(str(list_item['record_tc_out']))
            self.table_view.setItem(n, 6, newitem)
            newitem = QTableWidgetItem(str(list_item['shot_cut_source_in']))
            self.table_view.setItem(n, 7, newitem)
            newitem = QTableWidgetItem(str(list_item['shot_cut_source_out']))
            self.table_view.setItem(n, 8, newitem)
            newitem = QTableWidgetItem(str(list_item['cut_duration']))
            self.table_view.setItem(n, 9, newitem)
            newitem = QTableWidgetItem(str(list_item['pathurl']))
            self.table_view.setItem(n, 10, newitem)
            n += 1    
     
    def keyPressEvent(self, e):
        if (e.modifiers() & Qt.ControlModifier):
            selected = self.table_view.selectedRanges()
            if e.key() == Qt.Key_C: #copy
                s = "\t".join([str(self.table_view.horizontalHeaderItem(i).text()) for i in xrange(selected[0].leftColumn(), selected[0].rightColumn()+1)])
                s = s + '\n'

                for r in xrange(selected[0].topRow(), selected[0].bottomRow()+1):
                    for c in xrange(selected[0].leftColumn(), selected[0].rightColumn()+1):
                        try:
                            s += str(self.table_view.item(r,c).text()) + "\t"
                        except AttributeError:
                            s += "\t"
                    s = s[:-1] + "\n" #eliminate last '\t'
                self.clip.setText(s)

   
def selection_functions():
    sgauth()
    getsgprojectlist()
    setsgprojectcombolist()

def sgauth():
    # Prompts the user for their username and password
    win.user = ShotgunAuthenticator().get_user_from_prompt()        

    # Calling this method instead will retrieve the current Toolkit user that is
    # logged in the Desktop. This is used to be able to do single sign-on across
    # many Shotgun applications.
    #user = ShotgunAuthenticator().get_user()

    # Creates a Shotgun instance with the current session token (Toolkit doesn't
    # keep your password around)
    win.sg = win.user.create_sg_connection()

def getsgprojectlist():
    win.projects_dict = win.sg.find('Project',[],['id','name'])
    for project in win.projects_dict:
        project.pop('type')

def setsgprojectcombolist():
    print [d['id'] for d in win.projects_dict]
    text, ok = QInputDialog.getItem(win,'Shotgun project selection','Select project:', [d['name'] for d in win.projects_dict])
    if ok:
        for project in win.projects_dict:
            if project['name'] == text:
                win.selected_project = project
    win.openAction.setEnabled(True)
   
def create_shotgun_shots():
    data_seq = { 'project': {'type':'Project','id':win.selected_project['id']},'code': win.sequence_info['sec_name']}
    result_seq = win.sg.create('Sequence', data_seq)
    for sgshot in win.shot_list:
        data_shot = { 'project': {'type':'Project','id':win.selected_project['id']},'code': sgshot['shot_code'],'sg_cut_in': int(sgshot['shot_cut_source_in']),\
        'sg_cut_out': int(sgshot['shot_cut_source_out']), 'sg_cut_duration': int(sgshot['cut_duration']), 'sg_cut_order': int(sgshot['cut_order']), 'sg_sequence': {'type':'Sequence','id':result_seq['id']}}
        result_shot = win.sg.create('Shot', data_shot)
        sgshot['id'] = result_shot['id']
    win.sgversionsAction.setEnabled(True)

def create_shotgun_versions():
    create_version_entries()
    create_mov_files()
		
def create_mov_files():
    rvio_path = "/Applications/RV64.app/Contents/MacOS/rvio"
    temp_path = "/tmp/"
    rvio_args = "-outres 1280 720 -codec libx264 -outparams pix_fmt=yuv420p vcc:b=2000000000 vcc:g=30 vcc:profile=high vcc:bf=0"
    for shot in win.shot_list:
        time_range = "-t " + str(int(shot['in'])+1) + "-" + shot['out']
        output_path = "-o "+ temp_path + shot['shot_code'] + ".mov"
        try:
            #print rvio_path.split() + [shot['pathurl']] + output_path.split() + time_range.split() + rvio_args.split()
            proc = subprocess.call(rvio_path.split() + [shot['pathurl']] + output_path.split() + time_range.split() + rvio_args.split(),
                                    shell=False,
                                    stdout=subprocess.PIPE,
                                    )
            shot['mov_file'] = temp_path + shot['shot_code'] + ".mov"
            upload_shotgun_mov(shot)
        except:
            pass
    ###Creacion de quicktime para versiones con rvio
#/Applications/RV64.app/Contents/MacOS/rvio /Volumes/DATOS/BAJAJ_PULSAR/RODAJE_PULSAR/A001_C004_04157Q.RDC/A001_C004_04157Q_001.R3D \
#-o "PL_010_A (Resolve) (Resolve).mov" -outres 1280 720 -t 25-61 -codec libx264 -outparams pix_fmt=yuv420p vcc:b=2000000000 vcc:g=30 vcc:profile=high vcc:bf=0


def create_version_entries():
    for sgshot in win.shot_list:
        data_version = {
             'project': {'type':'Project','id':win.selected_project['id']},
             'code': "Version_"+sgshot['shot_code'],
             'entity': {'type':'Shot','id':sgshot['id']},
             }

        result_version = win.sg.create("Version",data_version)
        sgshot['version_id']=result_version['id']

def upload_shotgun_mov(shot):
    #for sgshot in win.shot_list:
    #    result_upload = win.sg.upload("Version",sgshot['version_id'],sgshot['mov_file'],"Version_"+sgshot['shot_code'])

    result_upload = win.sg.upload("Version",shot['version_id'],shot['mov_file'],"sg_uploaded_movie")


app = QApplication([])

#color scheme dark theme

app.setStyle('plastique')
newPalette = QPalette()
newPalette.setColor(QPalette.Button, QColor(80, 80, 80))
newPalette.setColor(QPalette.ButtonText, QColor(200, 200, 200))
newPalette.setColor(QPalette.Window, QColor(50, 50, 50))
newPalette.setColor(QPalette.Base, QColor(100, 100, 100))
newPalette.setColor(QPalette.Highlight, QColor(247, 147, 30))
newPalette.setColor(QPalette.Text, QColor(200, 200, 200))
newPalette.setColor(QPalette.WindowText, QColor(200, 200, 200))

'''
newPalette.setColor(QPalette.Shadow, QColor(200, 200, 200))
newPalette.setColor(QPalette.Light, QColor(200, 200, 200))
newPalette.setColor(QPalette.Midlight, QColor(200, 200, 200))
newPalette.setColor(QPalette.Mid, QColor(200, 200, 200))
'''

app.setPalette(newPalette)


win = XMLMainWindow()
win.show()

app.exec_()



###Creacion de quicktime para versiones con rvio
###/Applications/RV64.app/Contents/MacOS/rvio /Volumes/DATOS/BAJAJ_PULSAR/RODAJE_PULSAR/A001_C004_04157Q.RDC/A001_C004_04157Q_001.R3D -o "PL_010_A (Resolve) (Resolve).mov" -outres 1280 720 -t 25-61 -codec libx264 -outparams pix_fmt=yuv420p vcc:b=2000000000 vcc:g=30 vcc:profile=high vcc:bf=0

##Shotgun auth and gathering info
# from shotgun_api3 import Shotgun
# sg = Shotgun("https://configura.shotgunstudio.com",login="abraham",password="Levitin1978")
# sg = Shotgun("https://configura.shotgunstudio.com","API","04bce60d30b81100015f06eb4bd9b5c65cf975b8da7742ed1d9c6588c1caef23")
# all_projects = sg.find('Project',[],['id','name'])
# project_list = []
# for project in all_projects:
# 	project_list.append({project['name']:project['id']})
# shots = sg.find("Shot",[['project','is',{'type': 'Project', 'id': 68}]],['code','sg_sequence'])
# for shot in shots:
# 	print shot

# project_id = 68 # sin identidad en configura
# data = {
#     'project': {'type':'Project','id':project_id},
#     'code':'code field test',
#     'description': 'description test',
#     'sg_status_list':'rev',
#     'entity': {'type':'Shot','id':1352},
#     }

# version = sg.create("Version",data)
# print(version)
# quicktime = '/data/show/ne2/100_110/anim/01.mlk-02b.mov'
# version_id = 423
# result = sg.upload("Version",version_id,quicktime,"sg_uploaded_movie")
# print result
#data = { 'project': {'type':'Project','id':68},'code': 'sec_001','description': 'first secuence for test'}
#result = sg.create('Sequence', data)
#data = { 'project': {'type':'Project','id':68},'code': 'shot_001','description': 'kkkk','sg_cut_in': 10,\
# 'sg_cut_out': 20, 'sg_cut_duration': 10, 'sg_cut_order': 1, 'sg_sequence': {'type':'Sequence','id':21}}
#result = sg.create('Shot', data)



