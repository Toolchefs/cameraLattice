#                 Toolchefs ltd - Software Disclaimer
#
# Copyright 2014 Toolchefs Limited 
#
# The software, information, code, data and other materials (Software)
# contained in, or related to, these files is the confidential and proprietary
# information of Toolchefs ltd.
# The software is protected by copyright. The Software must not be disclosed,
# distributed or provided to any third party without the prior written
# authorisation of Toolchefs ltd.


import os
import re
import sys
import traceback

try:
    from PySide import QtGui, QtCore
    import PySide.QtGui as QtWidgets
    import shiboken
except ImportError:
    from PySide2 import QtGui, QtCore, QtWidgets
    import shiboken2 as shiboken

from maya import OpenMaya
from maya import cmds
from __builtin__ import False

LATTICE_MAYA_TYPE = 'mesh'
CAMERA_MAYA_TYPE = 'camera'
LATTICE_MESSAGE_ATTRIBUTE = 'camera'
DEFORMER_MESSAGE_ATTRIBUTE = 'deformerMessage'
LATTICE_TO_DEFORMER_MESSAGE_ATTRIBUTE = 'ldMessage'
INFLUENCE_MESSAGE_ATTRIBUTE = 'locatorMessage'
CAMERA_LATTICE_BASE_NAME = 'cameraLattice'
CAMERA_LATTICE_DEFORMER = 'tcCameraLatticeDeformer'
CAMERA_LATTICE_INFLUENCER = 'tcCameraLatticeInfluenceAreaLocator'

CAMERA_LATTICE_PARENT_ATTR = 'cameraLatticeParentAttr'
LATTICE_ACTIVE_ATTR = 'lActive'
INTERPOLATION_ATTR = 'interpolation'
SDIVISIONS_ATTR = 'sDivisions'
TDIVISIONS_ATTR = 'tDivisions'
MAX_BEZIER_RECURSION_ATTR = 'maxRecursion'
GATE_OFFSET_ATTR = 'gateOffset'

def _is_deformable(obj):
    if cmds.nodeType(obj) == "transform":
        shapes = cmds.listRelatives(obj, shapes=True)
        if not shapes:
            return False
        return bool(cmds.ls(shapes[0], type="deformableShape"))
    
    return bool(cmds.ls(obj, type="deformableShape"))

def _get_camera_shape(camera):
    if cmds.nodeType(camera) == CAMERA_MAYA_TYPE:
        return camera
    shapes = cmds.listRelatives(camera, shapes=True)
    if not shapes:
        return None
    if cmds.nodeType(shapes[0]) == CAMERA_MAYA_TYPE:
        return shapes[0]

def _is_lattice(item):
    if cmds.nodeType(item) == LATTICE_MAYA_TYPE:
        item = cmds.listRelatives(item, fullPath=True, parent=True)[0]
    return cmds.nodeType(item) == "transform" and cmds.objExists(item + '.' + CAMERA_LATTICE_PARENT_ATTR)

def _is_camera(item):
    return bool(_get_camera_shape(item))

def _get_unique_camera_lattice_name():
    counter = 1
    while cmds.objExists(CAMERA_LATTICE_BASE_NAME + str(counter)):
        counter += 1
    return CAMERA_LATTICE_BASE_NAME + str(counter)

def _get_connected_items(plug_name, with_plug=False, destination=False, types=[]):
    items = []
    selList = OpenMaya.MSelectionList()
    selList.add(plug_name)
    
    mPlug = OpenMaya.MPlug()
    selList.getPlug(0, mPlug) 
        
    mPlugArray = OpenMaya.MPlugArray()
    if mPlug.isArray():
        num = mPlug.numConnectedElements()
        thisPlugArray = OpenMaya.MPlugArray()
        for i in range(num):
            p = mPlug.connectionByPhysicalIndex(i)
            p.connectedTo(thisPlugArray, not destination, destination)
            for j in range(thisPlugArray.length()):
                mPlugArray.append(thisPlugArray[j])
    else:
        mPlug.connectedTo(mPlugArray, not destination, destination)
    
    dp = OpenMaya.MDagPath()
    for index in range(mPlugArray.length()):
        try:
            OpenMaya.MDagPath.getAPathTo(mPlugArray[index].node(), dp)    
            if with_plug:
                items.append(dp.fullPathName() + '.' + mPlugArray[index].partialName(False, False, False, False, False, True))
            else:
                if not types or (types and cmds.nodeType(dp.fullPathName()) in types):
                    items.append(dp.fullPathName())
        except RuntimeError:
            depFn = OpenMaya.MFnDependencyNode(mPlugArray[index].node())
            if with_plug:
                items.append(depFn.name() + '.' + mPlugArray[index].partialName(False, False, False, False, False, True))
            else:
                if not types or (types and cmds.nodeType(depFn.name()) in types):
                    items.append(depFn.name())
    return items

def _get_transform_from_camera_shape(item):
    if cmds.nodeType(item) == CAMERA_MAYA_TYPE:
        return cmds.listRelatives(item, fullPath=True, parent=True)[0]
    return item

def _get_camera(selection):
    for s in selection:
        if  _is_camera(s):
            return _get_transform_from_camera_shape(s)
        elif _is_lattice(s) and cmds.objExists(s + '.' + CAMERA_MAYA_TYPE):
            result = _get_connected_items(s + '.' + CAMERA_MAYA_TYPE)
            if result and _is_camera(result[0]):
                return _get_transform_from_camera_shape(result[0])
         
def _get_lattices_from_camera(camera):
    shape = _get_camera_shape(camera)
    messages = _get_connected_items(shape + '.message', with_plug=True, destination=True)
    if messages is None:
        return []
    
    lattices = []
    for m in messages:
        tokens = m.split('.')
        if tokens[1] == LATTICE_MESSAGE_ATTRIBUTE and _is_lattice(tokens[0]):
            lattices.append(tokens[0])
    return lattices
         
def _delete_lattice_deformers(lattice):
    deformers = _get_connected_items(lattice + '.message', destination=True, types=[CAMERA_LATTICE_DEFORMER])
    if deformers:
        cmds.delete(deformers)
        
def _get_selected_influencers():
    selection = cmds.ls(sl=True, l=True)
    influencers = []
    for s in selection:
        if cmds.nodeType(s)==CAMERA_LATTICE_INFLUENCER:
            influencers.append(s)
            continue
        
        shapes = cmds.listRelatives(s, shapes=True)
        if not shapes:
            continue
        
        if cmds.nodeType(shapes[0])==CAMERA_LATTICE_INFLUENCER:
            influencers.append(s)
        
    return influencers

def get_connected_index_attr(attr, array_attr):
    indices = cmds.getAttr(array_attr, mi=True)
    if not indices:
        return -1
    for index in indices:
        if cmds.isConnected(attr, array_attr + "[%d]" % index):
            return index
    return -1

def _get_next_index_for_attribute_array(attribute):
    indices = cmds.getAttr(attribute, mi=True)
    if indices is not None:
        indices.sort()
        return indices[-1]+1
    else:
        return 0
    
def _apply_influence_area_to_deformer(deformer, area):
    index = get_connected_index_attr(area + ".falloff", deformer + ".influenceFalloff")
    if index != -1:
        cmds.warning("tcCameraLattice: influence area already applied to " + deformer)
        return
    
    index =  _get_next_index_for_attribute_array(deformer + '.influenceMatrix')
    cmds.connectAttr(area + '.worldMatrix[0]', deformer + '.influenceMatrix[%d]' % index)
    cmds.connectAttr(area + '.falloff', deformer + '.influenceFalloff[%d]' % index)

def _apply_influence_area_to_lattice(lattice, area):
    if get_connected_index_attr(lattice + ".message", area + "." + INFLUENCE_MESSAGE_ATTRIBUTE) != -1:
        return False
    
    index = _get_next_index_for_attribute_array(area + "." + INFLUENCE_MESSAGE_ATTRIBUTE)
    cmds.connectAttr(lattice + ".message", area + ".%s[%d]" % (INFLUENCE_MESSAGE_ATTRIBUTE, index))
    
    deformers = _get_connected_items(lattice + '.message', destination=True, types=[CAMERA_LATTICE_DEFORMER])
    if not deformers:
        return True
    
    for d in deformers:
        _apply_influence_area_to_deformer(d, area)
        
    return True

def _create_influence_area(lattice):
    node = cmds.createNode(CAMERA_LATTICE_INFLUENCER, n=CAMERA_LATTICE_INFLUENCER+"Shape")
    
    camera = _get_camera([lattice])
    matrix = cmds.getAttr(camera+".worldMatrix[0]")
    
    transform = cmds.listRelatives(node, fullPath=True, parent=True)[0]
    cmds.addAttr(transform, ln="falloff", at="double", minValue=0, maxValue=1, defaultValue=0.5, keyable=True)
    cmds.setAttr(transform+".falloff", channelBox=True)
    cmds.connectAttr(transform+".falloff", node+".falloff")
    
    transform = cmds.rename(transform, CAMERA_LATTICE_INFLUENCER)
    
    x = matrix[12] + matrix[8] * -3
    y = matrix[13] + matrix[9] * -3
    z = matrix[14] + matrix[10] * -3
    cmds.setAttr(transform+'.tx', x)
    cmds.setAttr(transform+'.ty', y)
    cmds.setAttr(transform+'.tz', z)
    
    _apply_influence_area_to_lattice(lattice, transform)
    
    cmds.select(transform, r=True)
    return transform

def _get_all_influencers(lattice):
    shapes = _get_connected_items(lattice + '.message', destination=True, types=[CAMERA_LATTICE_INFLUENCER])
    return [cmds.listRelatives(node, fullPath=True, parent=True)[0] for node in shapes]

def _get_infuencer_full_path(lattice, influencer):
    influencers = _get_all_influencers(lattice)
    for i in influencers:
        if i.endswith(influencer):
            return i

def _disconnect_influencers(lattice, influencers):
    for i in influencers:
        fi = _get_infuencer_full_path(lattice, i)
        if not fi:
            continue
        
        index = get_connected_index_attr(lattice + ".message", fi + "." + INFLUENCE_MESSAGE_ATTRIBUTE)
        if index == -1:
            continue
        cmds.disconnectAttr(lattice + ".message", fi + ".%s[%d]" % (INFLUENCE_MESSAGE_ATTRIBUTE, index))
        
        deformers = _get_connected_items(lattice + '.message', destination=True, types=[CAMERA_LATTICE_DEFORMER])
        for d in deformers:
            index = get_connected_index_attr(fi + ".falloff", d + ".influenceFalloff")
            if index == -1:
                cmds.warning("tcCameraLattice: something is wrong with your influece are to deformer connections.")
                continue
            
            cmds.disconnectAttr(fi + ".falloff", d + ".influenceFalloff[%d]" % index)
            cmds.disconnectAttr(fi + ".worldMatrix[0]", d + ".influenceMatrix[%d]" % index)

def _finalise_attribute(attribute):
    cmds.setAttr(attribute, l=True)
    cmds.setAttr(attribute, k=False)
    cmds.setAttr(attribute, channelBox=False)

def _finalise_lattice(lattice, x_div, y_div):
    cmds.setAttr(lattice + '.sz', 0)
    
    _finalise_attribute(lattice + '.tx')
    _finalise_attribute(lattice + '.ty')
    _finalise_attribute(lattice + '.rx')
    _finalise_attribute(lattice + '.ry')
    _finalise_attribute(lattice + '.rz')
    _finalise_attribute(lattice + '.sz')
    
    _finalise_attribute(lattice + '.sx')
    _finalise_attribute(lattice + '.sy')
    _finalise_attribute(lattice + '.tz')

    node = cmds.createNode('addDoubleLinear')
    _finalise_attribute(node + '.input1')
    _finalise_attribute(node + '.input2')
    for i in range(x_div * y_div):
        cmds.connectAttr(node + ".output", lattice + ".pt[" + str(i) + "].pz")

def _create_camera_lattice(camera, x_div, y_div):
    selection = cmds.ls(sl=True, l=True)
    
    cmds.select(cl=True)
    plane_objects = cmds.polyPlane(w=1, h=1, sx=x_div - 1, sy=y_div - 1, ax=[0, 0, 1], cuv=0, ch=1)
    cmds.delete(plane_objects[0], ch=True)
    lattice = plane_objects[0]
    
    cmds.setAttr(lattice + ".overrideEnabled", 1)
    cmds.setAttr(lattice + ".overrideShading", 0)
    
    max_div = x_div if x_div > y_div else y_div
    
    cmds.addAttr(lattice, ln=CAMERA_LATTICE_PARENT_ATTR, numberOfChildren=7, attributeType='compound')
    cmds.addAttr(lattice, ln=LATTICE_ACTIVE_ATTR, at="double", parent=CAMERA_LATTICE_PARENT_ATTR, maxValue=1, minValue=0, defaultValue=1)
    cmds.addAttr(lattice, ln=LATTICE_MESSAGE_ATTRIBUTE, at="message", parent=CAMERA_LATTICE_PARENT_ATTR)
    cmds.addAttr(lattice, ln=INTERPOLATION_ATTR, at='enum', enumName='linear:bezier', parent=CAMERA_LATTICE_PARENT_ATTR)
    cmds.addAttr(lattice, ln=SDIVISIONS_ATTR, at="long", parent=CAMERA_LATTICE_PARENT_ATTR, minValue=3)
    cmds.addAttr(lattice, ln=TDIVISIONS_ATTR, at="long", parent=CAMERA_LATTICE_PARENT_ATTR, minValue=3)
    cmds.addAttr(lattice, ln=MAX_BEZIER_RECURSION_ATTR, at="long", parent=CAMERA_LATTICE_PARENT_ATTR, maxValue=max_div - 2, minValue=1, keyable=True)
    cmds.addAttr(lattice, ln=GATE_OFFSET_ATTR, at="double", parent=CAMERA_LATTICE_PARENT_ATTR, maxValue=1, minValue=0, defaultValue=0.1, keyable=True)
    
    cmds.setAttr(lattice + "." + SDIVISIONS_ATTR, x_div)
    cmds.setAttr(lattice + "." + TDIVISIONS_ATTR, y_div)
    cmds.setAttr(lattice + "." + INTERPOLATION_ATTR, channelBox=True)
    cmds.setAttr(lattice + "." + MAX_BEZIER_RECURSION_ATTR, 4 if max_div / 2 > 4 else max_div / 2)
    cmds.setAttr(lattice + "." + LATTICE_ACTIVE_ATTR, channelBox=False)
    
    lattice = cmds.rename(lattice, _get_unique_camera_lattice_name())
    cmds.parent(lattice, camera)
    cmds.setAttr(lattice + '.tx', 0)
    cmds.setAttr(lattice + '.ty', 0)
    cmds.setAttr(lattice + '.tz', 0)
    cmds.setAttr(lattice + '.rx', 0)
    cmds.setAttr(lattice + '.ry', 0)
    cmds.setAttr(lattice + '.rz', 0)
    
    converter = cmds.createNode('tcCameraLatticeTranslator')
    cmds.connectAttr(camera + '.nearClipPlane', converter + '.inNearClipPlane')
    cmds.connectAttr(camera + '.focalLength', converter + '.inFocalLength')
    cmds.connectAttr(camera + '.horizontalFilmAperture', converter + '.inHorizontalFilmAperture')
    cmds.connectAttr(camera + '.verticalFilmAperture', converter + '.inVerticalFilmAperture')
    cmds.connectAttr(camera + '.orthographic', converter + '.inOrtho')
    cmds.connectAttr(camera + '.orthographicWidth', converter + '.inOrthographicWidth')
    cmds.connectAttr(converter + '.outScaleX', lattice + '.scaleX')
    cmds.connectAttr(converter + '.outScaleY', lattice + '.scaleY')
    cmds.connectAttr(converter + '.outTranslateZ', lattice + '.translateZ')
    
    camera_shape = cmds.listRelatives(camera, shapes=True)[0]
    cmds.connectAttr(camera_shape + '.message', lattice + '.' + LATTICE_MESSAGE_ATTRIBUTE)
    
    _finalise_lattice(lattice, x_div, y_div)
    
    cmds.select(lattice, r=True)
    
    return cmds.ls(lattice, l=True)[0]
    
def _get_all_affected_objects(lattice):
    cameraLatticeDeformers = _get_connected_items(lattice + '.message', destination=True, types=[CAMERA_LATTICE_DEFORMER])
    #get all objects connected
    objects = {}
    for cld in cameraLatticeDeformers:
        obj = _get_connected_items(cld + '.' + DEFORMER_MESSAGE_ATTRIBUTE, destination=False)
        if obj:
            objects[cld] = obj[0]
    return objects

def _apply_camera_lattice(object, lattice):
    messages = _get_connected_items(lattice + '.' + LATTICE_MESSAGE_ATTRIBUTE, with_plug=False, destination=False)
    if not messages or len(messages) > 1:
        raise RuntimeError('Camera Lattice: could not find camera shape from lattice.')
    
    deformer = str(cmds.deformer(object, type=CAMERA_LATTICE_DEFORMER)[0])
    if not deformer:
        raise RuntimeError('Camera Lattice: could not create ' + CAMERA_LATTICE_DEFORMER + '.')

    cmds.connectAttr(lattice + '.outMesh', deformer + '.il')
    cmds.connectAttr(lattice + '.' + INTERPOLATION_ATTR, deformer + '.i')
    cmds.connectAttr(lattice + '.' + SDIVISIONS_ATTR, deformer + '.ss')
    cmds.connectAttr(lattice + '.' + TDIVISIONS_ATTR, deformer + '.ts')
    cmds.connectAttr(lattice + '.' + MAX_BEZIER_RECURSION_ATTR, deformer + '.mbr')
    cmds.connectAttr(lattice + '.message', deformer + "." + LATTICE_TO_DEFORMER_MESSAGE_ATTRIBUTE)
    cmds.connectAttr(lattice + '.' + LATTICE_ACTIVE_ATTR, deformer + '.envelope')
    cmds.connectAttr(lattice + '.' + GATE_OFFSET_ATTR, deformer + '.gateOffset')

    cmds.connectAttr(object + ".worldMatrix[0]", deformer + '.om')
    cmds.connectAttr(str(messages[0]) + ".worldMatrix[0]", deformer + '.cm')
    cmds.connectAttr(str(messages[0]) + ".focalLength", deformer + '.iFL')
    cmds.connectAttr(str(messages[0]) + ".horizontalFilmAperture", deformer + '.iHF')
    cmds.connectAttr(str(messages[0]) + ".verticalFilmAperture", deformer + '.iVF')
    cmds.connectAttr(str(messages[0]) + ".orthographicWidth", deformer + '.iOW')
    cmds.connectAttr(str(messages[0]) + ".orthographic", deformer + '.iO')
    
    cmds.connectAttr(object + ".message", deformer + "." + DEFORMER_MESSAGE_ATTRIBUTE)
    
    for influencer in _get_all_influencers(lattice):
        _apply_influence_area_to_deformer(deformer, influencer)

    return deformer
    

##########################
######GUI#################
##########################

def _build_layout(horizontal):
    if (horizontal):
        layout = QtWidgets.QHBoxLayout()
    else:
        layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(QtCore.QMargins(2, 2, 2, 2))
    return layout


def _create_separator(vertical=False):
    separator = QtWidgets.QFrame()
    if vertical:
        separator.setFrameShape(QtWidgets.QFrame.VLine)
    else:
        separator.setFrameShape(QtWidgets.QFrame.HLine)
    separator.setFrameShadow(QtWidgets.QFrame.Sunken)
    return separator


def _get_icons_path():
    tokens = __file__.split(os.path.sep)
    return os.path.sep.join(tokens[:-1] + ['icons']) + os.path.sep


class LineWidget(QtWidgets.QWidget):
    def __init__(self, label, widget, width=90, parent=None):
        super(LineWidget, self).__init__(parent=parent)

        self._main_layout = _build_layout(True)
        self.setLayout(self._main_layout)

        label = QtWidgets.QLabel(label)
        label.setFixedWidth(width)
        self._main_layout.addWidget(label)
        self._main_layout.addWidget(widget)

class CameraLatticeCreateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(CameraLatticeCreateDialog, self).__init__(parent)
        self.setWindowTitle("Camera Lattice Dialog")
        self.setObjectName("Camera Lattice Dialog")
        
        self.setFixedSize(400, 130)
        
        self._main_layout = _build_layout(False)
        self.setLayout(self._main_layout)
        
        self._x_div = QtWidgets.QSpinBox()
        self._x_div.setSingleStep(1)
        self._x_div.setMinimum(3)
        self._x_div.setMaximum(100)
        self._x_div.setValue(10)
        self._main_layout.addWidget(LineWidget("X Division:", self._x_div))
        
        self._y_div = QtWidgets.QSpinBox()
        self._y_div.setSingleStep(1)
        self._y_div.setMinimum(3)
        self._y_div.setMaximum(100)
        self._y_div.setValue(10)
        self._main_layout.addWidget(LineWidget("Y Division:", self._y_div))
        
        # OK and Cancel buttons
        self._buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal, self)
        self._main_layout.addWidget(self._buttons)
        
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        
    def get_divs(self):
        return (self._x_div.value(), self._y_div.value())
        
    @staticmethod
    def get_result(parent=None):
        dialog = CameraLatticeCreateDialog(parent)
        result = dialog.exec_()
        divs = dialog.get_divs()
        return (divs[0], divs[1], result == QtWidgets.QDialog.Accepted)
        
        
class CameraLatticeTreeWidgetItem(QtWidgets.QTreeWidgetItem):
    def __init__(self):
        super(CameraLatticeTreeWidgetItem, self).__init__(QtWidgets.QTreeWidgetItem.UserType + 1)
        self.camera_lattice_deformer_node = None
        self.object_full_path = None
        
class CameraLatticeControlsWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(CameraLatticeControlsWidget, self).__init__(parent)
        self.setWindowTitle('Camera Lattice Controls')
        self.setObjectName('Camera Lattice Controls')
        
        self._lattice = None
        self._script_jobs = []
        self._interpolation_changed_from_GUI = False
        self._max_bezier_recursion_changed_from_GUI = False
        
        self._main_layout = _build_layout(False)
        self.setLayout(self._main_layout)
        
        self._create_widgets()
        self._connect_signals()
    
    def _build_affected_object_widget(self):
        container = QtWidgets.QWidget()
        h_layout = _build_layout(True)
        container.setLayout(h_layout)
        
        self._objects_tree = QtWidgets.QTreeWidget()
        self._objects_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._objects_tree.header().close()
        h_layout.addWidget(self._objects_tree)
        
        v_layout = _build_layout(False)
        h_layout.addLayout(v_layout)
        
        self._add_object_button = QtWidgets.QPushButton()
        self._add_object_button.setFixedSize(40, 40)
        self._add_object_button.setIcon(QtGui.QIcon(_get_icons_path() + 'addObject.png'))
        self._add_object_button.setIconSize(QtCore.QSize(40, 40))
        self._add_object_button.setToolTip('Add selected object to camera lattice')
        
        self._remove_object_button = QtWidgets.QPushButton()
        self._remove_object_button.setFixedSize(40, 40)
        self._remove_object_button.setIcon(QtGui.QIcon(_get_icons_path() + 'deleteObject.png'))
        self._remove_object_button.setIconSize(QtCore.QSize(40, 40))
        self._remove_object_button.setToolTip('Remove object from camera lattice')
        
        v_layout.addWidget(self._add_object_button)
        v_layout.addWidget(self._remove_object_button)
        v_layout.addWidget(QtWidgets.QWidget(), stretch=1)
        
        return container
    
    
    def _build_influece_areas_widget(self):
        container = QtWidgets.QWidget()
        h_layout = _build_layout(True)
        container.setLayout(h_layout)
        
        self._influences_tree = QtWidgets.QTreeWidget()
        self._influences_tree.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._influences_tree.header().close()
        h_layout.addWidget(self._influences_tree)
        
        v_layout = _build_layout(False)
        h_layout.addLayout(v_layout)
        
        self._create_influencer_button = QtWidgets.QPushButton()
        self._create_influencer_button.setFixedSize(40, 40)
        self._create_influencer_button.setIcon(QtGui.QIcon(_get_icons_path() + 'createInfluencer.png'))
        self._create_influencer_button.setIconSize(QtCore.QSize(40, 40))
        self._create_influencer_button.setToolTip('Create influence area ond add it to camera lattice')
        
        self._add_influencer_button = QtWidgets.QPushButton()
        self._add_influencer_button.setFixedSize(40, 40)
        self._add_influencer_button.setIcon(QtGui.QIcon(_get_icons_path() + 'addInfluencer.png'))
        self._add_influencer_button.setIconSize(QtCore.QSize(40, 40))
        self._add_influencer_button.setToolTip('Add selected influence area to camera lattice')
        
        self._remove_influencer_button = QtWidgets.QPushButton()
        self._remove_influencer_button.setFixedSize(40, 40)
        self._remove_influencer_button.setIcon(QtGui.QIcon(_get_icons_path() + 'deleteInfluencer.png'))
        self._remove_influencer_button.setIconSize(QtCore.QSize(40, 40))
        self._remove_influencer_button.setToolTip('Remove influence area from camera lattice')
        
        v_layout.addWidget(self._create_influencer_button)
        v_layout.addWidget(self._add_influencer_button)
        v_layout.addWidget(self._remove_influencer_button)
        v_layout.addWidget(QtWidgets.QWidget(), stretch=1)
        
        return container
    
    
    def _create_widgets(self):
        _active_parent = QtWidgets.QWidget()
        h_layout = _build_layout(True)
        _active_parent.setLayout(h_layout)
        
        self._active_group = QtWidgets.QButtonGroup(_active_parent) 
        self._on_button = QtWidgets.QRadioButton("On")
        self._on_button.setChecked(True)
        self._active_group.addButton(self._on_button)
        self._off_button = QtWidgets.QRadioButton("Off")
        self._active_group.addButton(self._off_button)
        h_layout.addWidget(self._on_button)
        h_layout.addWidget(self._off_button)
        h_layout.addWidget(QtWidgets.QWidget(), 1)
        self._main_layout.addWidget(LineWidget("Active:", _active_parent))
        
        self._interpolation = QtWidgets.QComboBox()
        self._interpolation.addItem("Linear")
        self._interpolation.addItem("Bezier")
        self._main_layout.addWidget(LineWidget("Interpolation:", self._interpolation))
        
        self._max_bezier_recursion = QtWidgets.QSpinBox()
        self._max_bezier_recursion_lined_widget = LineWidget("Max Recursion:", self._max_bezier_recursion) 
        self._main_layout.addWidget(self._max_bezier_recursion_lined_widget)
        
        tab_widget = QtWidgets.QTabWidget()
        tab_widget.addTab(self._build_affected_object_widget(), "Affected Objects")
        tab_widget.addTab(self._build_influece_areas_widget(), "Influence Areas")
        
        self._main_layout.addWidget(tab_widget)
        
        self._main_layout.addWidget(_create_separator(False))
        
        h_layout = _build_layout(True)
        self._main_layout.addLayout(h_layout)
        
        self._select_all_points_button = QtWidgets.QPushButton("Select All Points")
        self._select_all_edited_points_button = QtWidgets.QPushButton("Select All Edited Points")
        self._select_all_edited_points_button.setToolTip('Select all points not at rest position')
        self._select_all_static_edited_points_button = QtWidgets.QPushButton("Select All Static Edited Points")
        self._select_all_static_edited_points_button.setToolTip('Select all points not at rest position and no animation')
        self._select_all_animated_points_button = QtWidgets.QPushButton("Select All Animated Points")
        self._select_all_animated_points_button.setToolTip('Select all animated points')
        self._invert_selection_button = QtWidgets.QPushButton("Invert Points Selection")
        self._reset_selected_points_to_initial_position = QtWidgets.QPushButton("Reset Selected Points")
        self._reset_lattice_button = QtWidgets.QPushButton("Reset All Points")
        
        v_layout = _build_layout(False)
        h_layout.addLayout(v_layout)
        v_layout.addWidget(self._select_all_points_button, stretch=1)
        v_layout.addWidget(self._select_all_edited_points_button, stretch=1)
        v_layout.addWidget(self._select_all_animated_points_button, stretch=1)
        v_layout.addWidget(self._select_all_static_edited_points_button, stretch=1)
        v_layout.addWidget(self._invert_selection_button, stretch=1)
        v_layout.addWidget(_create_separator(False), stretch=1)
        v_layout.addWidget(self._reset_selected_points_to_initial_position, stretch=1)
        v_layout.addWidget(self._reset_lattice_button, stretch=1)
    
        v_layout = _build_layout(False) 
        self._key_selected_on_x_button = QtWidgets.QPushButton("Key On X")
        self._key_selected_on_x_button.setFixedWidth(80)
        self._key_selected_on_x_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self._key_selected_on_y_button = QtWidgets.QPushButton("Key On Y")
        self._key_selected_on_y_button.setFixedWidth(80)
        self._key_selected_on_y_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        self._key_selected_button = QtWidgets.QPushButton("Key On XY")
        self._key_selected_button.setFixedWidth(80)
        self._key_selected_button.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Expanding)
        
        v_layout.addWidget(self._key_selected_on_x_button)
        v_layout.addWidget(self._key_selected_on_y_button)
        v_layout.addWidget(self._key_selected_button)
        
        h_layout.addWidget(_create_separator(True))
        h_layout.addLayout(v_layout)
        
    def _connect_signals(self):
        self._active_group.buttonClicked.connect(self._active_group_clicked)
        
        self._objects_tree.itemClicked.connect(self._objects_selection_changed)
        self._influences_tree.itemClicked.connect(self._influences_selection_changed)
        self._interpolation.currentIndexChanged.connect(self._interpolation_changed)
        
        self._max_bezier_recursion.valueChanged.connect(self._max_bezier_recursion_changed)
        self._max_bezier_recursion_lined_widget.setVisible(False)
        
        self._add_object_button.clicked.connect(self._add_object_button_clicked)
        self._remove_object_button.clicked.connect(self._remove_object_button_clicked)
        
        self._create_influencer_button.clicked.connect(self._create_influencer_button_clicked)
        self._add_influencer_button.clicked.connect(self._add_influencer_button_clicked)
        self._remove_influencer_button.clicked.connect(self._remove_influencer_button_clicked)
        
        self._select_all_points_button.clicked.connect(self._select_all_points_button_clicked)
        self._select_all_edited_points_button.clicked.connect(self._select_all_edited_points_button_clicked)
        self._select_all_animated_points_button.clicked.connect(self._select_all_animated_points_button_clicked)
        self._select_all_static_edited_points_button.clicked.connect(self._select_all_static_edited_points_button_clicked)
        self._invert_selection_button.clicked.connect(self._invert_selection_button_clicked)
        self._reset_selected_points_to_initial_position.clicked.connect(self._reset_selected_points_to_initial_position_clicked)
        self._reset_lattice_button.clicked.connect(self._reset_lattice_button_clicked)
        self._key_selected_button.clicked.connect(self._key_selected_button_clicked)
        self._key_selected_on_x_button.clicked.connect(self._key_selected_on_x_button_clicked)
        self._key_selected_on_y_button.clicked.connect(self._key_selected_on_y_button_clicked)
        
    def _pre_lattice_point_selection(self):
        cmds.select(self._lattice, r=True)
        cmds.hilite(self._lattice)
        cmds.selectType(ocm=True, alc=False)
        cmds.selectType(ocm=True, vertex=True)
    
    @staticmethod
    def _is_value_changed(val1, val2):
        return (val1 < val2 - 0.0001) or (val1 > val2 + 0.0001)
    
    def _get_lattice_divisions(self):
        sD = cmds.getAttr(self._lattice + ".sDivisions")
        tD = cmds.getAttr(self._lattice + ".tDivisions")
        return sD, tD
    
    def _is_item_in_affected_objs(self, obj):
        for i in range(self._objects_tree.topLevelItemCount()):
            item = self._objects_tree.topLevelItem(i)
            if item.object_full_path == obj:
                return True
        return False
    
    def _active_group_clicked(self):
        if self._on_button.isChecked():
            cmds.setAttr(self._lattice + "." + LATTICE_ACTIVE_ATTR, 1)
        else:
            cmds.setAttr(self._lattice + "." + LATTICE_ACTIVE_ATTR, 0)

    def _create_influencer_button_clicked(self):
        cmds.undoInfo(openChunk=True, chunkName='tcCreateInfluenceAreaToCameraLattice')
        try:
            influencer = _create_influence_area(self._lattice)
            item = self._create_influencer_tree_item(influencer)
            self._influences_tree.addTopLevelItem(item)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)

    def _add_influencer_button_clicked(self):
        cmds.undoInfo(openChunk=True, chunkName='tcAddInfluenceAreaToCameraLattice')
        try:
            for influencer in _get_selected_influencers():
                if _apply_influence_area_to_lattice(self._lattice, influencer):
                    item = self._create_influencer_tree_item(influencer)
                    self._influences_tree.addTopLevelItem(item)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)

    def _remove_influencer_button_clicked(self):
        items = self._influences_tree.selectedItems()
        nodes = []
        for item in items:
            index = self._influences_tree.indexFromItem(item)
            node = _get_infuencer_full_path(self._lattice, item.influencer)
            if node:
                nodes.append(node)
            self._influences_tree.takeTopLevelItem(index.row())
        
        if nodes:
            cmds.undoInfo(openChunk=True, chunkName='tcRemoveInfluenceAreaFromCameraLattice')
            _disconnect_influencers(self._lattice, nodes)
            cmds.undoInfo(closeChunk=True)
        
        self._remove_influencer_button.setEnabled(bool(self._influences_tree.selectedItems()))
    
    def _add_object_button_clicked(self):
        selection = cmds.ls(sl=True, l=True, type="transform")
        if not selection:
            cmds.warning("Camera Lattice: Please select mesh transforms and add them to the lattice.")
            return
        
        cmds.undoInfo(openChunk=True, chunkName='tcAddObjectToCameraLattice')
        try:
            for s in selection:
                #if the lattice is selected then skip it
                if _is_lattice(s):
                    cmds.warning('Camera Lattice: Cannot add camera lattices to the list of the affected objects.')
                    continue
                
                if not _is_deformable(s):
                    cmds.warning('Camera Lattice: %s is not a deformable object.' % s)
                    continue
                
                if self._is_item_in_affected_objs(s):
                    cmds.warning('Camera Lattice: This object is already affected by this lattice.')
                    continue
                
                deformer = _apply_camera_lattice(s, self._lattice)
                item = self._create_object_tree_item(deformer, s)
                self._objects_tree.addTopLevelItem(item)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
    
    def _remove_object_button_clicked(self):
        items = self._objects_tree.selectedItems()
        nodes = []
        for item in items:
            index = self._objects_tree.indexFromItem(item)
            nodes.append(item.camera_lattice_deformer_node)
            self._objects_tree.takeTopLevelItem(index.row())
        
        if nodes:
            cmds.undoInfo(openChunk=True, chunkName='tcRemoveObjectFromCameraLattice')
            try:
                cmds.delete(nodes)
            except:
                traceback.print_exc(file=sys.stdout)
                
            cmds.undoInfo(closeChunk=True)
        
        self._remove_object_button.setEnabled(bool(self._objects_tree.selectedItems()))
    
    def _select_all_points_button_clicked(self):
        sD, tD = self._get_lattice_divisions()
        
        cmds.undoInfo(openChunk=True, chunkName='tcSelectAllCameraLatticePoints')
        try:
            self._pre_lattice_point_selection()
            cmds.select(self._lattice + ".vtx[0:%d]" % (sD * tD - 1), r=True)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
        
    def _select_all_static_edited_points_button_clicked(self):
        sD, tD = self._get_lattice_divisions()
        
        x_step = 1.0 / (sD - 1)
        y_step = 1.0 / (tD - 1)
        offset = 0.5
        
        cmds.undoInfo(openChunk=True, chunkName='tcSelectAllCameraLatticeEditedPoints')
        try:
            self._pre_lattice_point_selection()
            cmds.select(cl=True)
            
            for t in range(tD):
                for s in range(sD):
                    attr_name = self._build_point_string(s, t, sD)
                    vector = cmds.xform(attr_name, q=True, translation=True)
                    edited = self._is_value_changed(vector[0], s * x_step - offset) or self._is_value_changed(vector[1], t * y_step - offset)
                    index = s + t * sD
                    animated = cmds.listConnections(self._lattice + ".pnts[%d].pntx" % index) or cmds.listConnections(self._lattice + ".pnts[%d].pnty" % index)
                    if edited and not animated:                        
                        cmds.select(attr_name, add=True)
        except:                    
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
    
    def _select_all_edited_points_button_clicked(self):
        sD, tD = self._get_lattice_divisions()
        
        x_step = 1.0 / (sD - 1)
        y_step = 1.0 / (tD - 1)
        offset = 0.5
        
        cmds.undoInfo(openChunk=True, chunkName='tcSelectAllCameraLatticeEditedPoints')
        try:
            self._pre_lattice_point_selection()
            cmds.select(cl=True)
            
            for t in range(tD):
                for s in range(sD):
                    attr_name = self._build_point_string(s, t, sD)
                    vector = cmds.xform(attr_name, q=True, translation=True)
                    if (self._is_value_changed(vector[0], s * x_step - offset) or 
                        self._is_value_changed(vector[1], t * y_step - offset)):
                        cmds.select(attr_name, add=True)
        except:                    
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
        
    def _select_all_animated_points_button_clicked(self):
        sD, tD = self._get_lattice_divisions()
        
        x_step = 1.0 / (sD - 1)
        y_step = 1.0 / (tD - 1)
        offset = 0.5
        
        cmds.undoInfo(openChunk=True, chunkName='tcSelectAllCameraLatticeAnimatedPoints')
        try:
            self._pre_lattice_point_selection()
            cmds.select(cl=True)
            for t in range(tD):
                for s in range(sD):
                    index = s + t * sD
                    if (cmds.listConnections(self._lattice + ".pnts[%d].pntx" % index) or 
                        cmds.listConnections(self._lattice + ".pnts[%d].pnty" % index)):
                        cmds.select(self._lattice + ".pnts[%d]" % index, add=True)
        except:                    
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
    
    def _invert_selection_button_clicked(self):
        selection = cmds.ls(sl=True, fl=True, l=True)
        if not selection:
            self._select_all_points_button_clicked()
            return
        
        if not self._lattice + ".vtx" in selection[0]: 
            cmds.error('Camera Lattice: no lattice points selected. Cannot inver selection.')
            return
        
        sD, tD = self._get_lattice_divisions()
        sel_set = set([str(s) for s in selection])
        cmds.undoInfo(openChunk=True, chunkName='tcInvertCameraLatticePointSelection')
        try:
            self._pre_lattice_point_selection()
            cmds.select(cl=True)
            for s in range(sD):
                for t in range(tD):
                    pt = self._build_point_string(s, t, sD)
                    if not pt in sel_set:
                        cmds.select(pt, add=True)
        except:                    
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
    
    @staticmethod
    def get_point_index_from_string(item):
         match = re.findall('(?<=\[)\d+(?=\])', item)
         return int(match[0])
    
    def _reset_selected_points_to_initial_position_clicked(self):
        selection = cmds.ls(sl=True, fl=True, l=True)
        if not selection:
            return
        
        if not self._lattice + ".vtx" in selection[0]: 
            cmds.error('Camera Lattice: no lattice points selected.')
            return
        
        sD, tD = self._get_lattice_divisions()
        
        x_step = 1.0 / (sD - 1)
        y_step = 1.0 / (tD - 1)
        offset = 0.5
        
        cmds.undoInfo(openChunk=True, chunkName='tcResetSelectedCameraLatticePoints')
        try:
            for pt in selection:
                cmds.setAttr(pt + '.pntx', 0.0)
                cmds.setAttr(pt + '.pnty', 0.0)
        except:                    
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True) 
    
    def _reset_lattice_button_clicked(self):
        sD, tD = self._get_lattice_divisions()
        
        x_step = 1.0 / (sD - 1)
        y_step = 1.0 / (tD - 1)
        offset = 0.5
        
        cmds.undoInfo(openChunk=True, chunkName='tcResetCameraLatticePoints')
        try:
            for s in range(sD):
                for t in range(tD):
                    vrt = self._build_point_string(s, t, sD)
                    cmds.setAttr(vrt + '.pntx', 0.0)
                    cmds.setAttr(vrt + '.pnty', 0.0)
        except:                    
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
    
    def _key_selected_on_x_button_clicked(self):
        selection = cmds.ls(sl=True, fl=True, l=True)
        if not selection:
            return
        
        if not self._lattice + ".vtx" in selection[0]: 
            cmds.error('Camera Lattice: no lattice points selected. Cannot key points.')
            return
        
        cmds.undoInfo(openChunk=True, chunkName='tcKeyCameraLatticePointsOnX')
        try:
            for s in selection:
                cmds.setKeyframe(s.replace('.vtx[', '.pnts[') + '.pntx', cp=True)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
        
    def _key_selected_on_y_button_clicked(self):
        selection = cmds.ls(sl=True, fl=True, l=True)
        if not selection:
            return
        
        if not self._lattice + ".vtx" in selection[0]: 
            cmds.error('Camera Lattice: no lattice points selected. Cannot key points.')
            return
        
        cmds.undoInfo(openChunk=True, chunkName='tcKeyCameraLatticePointsOnY')
        try:
            for s in selection:
                cmds.setKeyframe(s.replace('.vtx[', '.pnts[') + '.pnty', cp=True)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
    
    def _key_selected_button_clicked(self):
        selection = cmds.ls(sl=True, fl=True, l=True)
        if not selection:
            return
        
        if not self._lattice + ".vtx" in selection[0]: 
            cmds.error('Camera Lattice: no lattice points selected. Cannot key points.')
            return
        
        cmds.undoInfo(openChunk=True, chunkName='tcKeyCameraLatticePointsOnXY')
        try:
            for s in selection:
                cmds.setKeyframe(s.replace('.vtx[', '.pnts[') + '.pntx', cp=True)
                cmds.setKeyframe(s.replace('.vtx[', '.pnts[') + '.pnty', cp=True)
        except:
            traceback.print_exc(file=sys.stdout)
        cmds.undoInfo(closeChunk=True)
        
    def clear_object_tree(self):
        self._objects_tree.clear()
    
    def clear_influence_tree(self):
        self._influences_tree.clear()
        
    def _objects_selection_changed(self):
        items = self._objects_tree.selectedItems()
        self._remove_object_button.setEnabled(bool(items))
        
        objs = [i.object_full_path for i in items] 
        cmds.select(objs, r=True)

    def _influences_selection_changed(self):
        items = self._influences_tree.selectedItems()
        self._remove_influencer_button.setEnabled(bool(items))
        
        objs = [i.influencer for i in items] 
        cmds.select(objs, r=True)
        
    def _interpolation_changed(self):
        self._interpolation_changed_from_GUI = True
        cmds.setAttr(self._lattice + '.' + INTERPOLATION_ATTR, self._interpolation.currentIndex())
        self._max_bezier_recursion_lined_widget.setVisible(self._interpolation.currentIndex() == 1)
        
    def _max_bezier_recursion_changed(self):
        self._max_bezier_recursion_changed_from_GUI = True
        cmds.setAttr(self._lattice + '.' + MAX_BEZIER_RECURSION_ATTR, self._max_bezier_recursion.value())
        
    def _create_object_tree_item(self, deformer, object):
        item = CameraLatticeTreeWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        item.setText(0, object.split('|')[-1])
        item.setToolTip(0, object)
        item.camera_lattice_deformer_node = deformer
        item.object_full_path = object
        return item

    def _create_influencer_tree_item(self, influencer):
        item = CameraLatticeTreeWidgetItem()
        item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable)
        item.setText(0, influencer.split('|')[-1])
        item.setToolTip(0, influencer)
        item.influencer = influencer
        return item
        
    def set_lattice(self, lattice):
        self._lattice = lattice
        
        self.kill_script_jobs()
        self._start_script_jobs()

        active = cmds.getAttr(lattice + '.' + LATTICE_ACTIVE_ATTR)
        self._on_button.setChecked(active)
        self._off_button.setChecked(not active)
        
        #set interpolation value
        interpolation = cmds.getAttr(lattice + '.' + INTERPOLATION_ATTR)
        self._interpolation.setCurrentIndex(interpolation)
        
        #set maximum bezier recursion
        max_recursion = cmds.getAttr(lattice + '.' + MAX_BEZIER_RECURSION_ATTR)
        min = cmds.attributeQuery(MAX_BEZIER_RECURSION_ATTR, node=lattice, minimum=True)
        max = cmds.attributeQuery(MAX_BEZIER_RECURSION_ATTR, node=lattice, maximum=True)
        self._max_bezier_recursion.setValue(max_recursion)
        self._max_bezier_recursion.setMaximum(int(max[0]))
        self._max_bezier_recursion.setMinimum(int(min[0]))
        
        self._max_bezier_recursion_lined_widget.setVisible(interpolation == 1)
        
        self._refresh_object_tree()
        self._refresh_influence_tree()
        
    def _refresh_object_tree(self):
        self.clear_object_tree()
        #populate tree
        objects = _get_all_affected_objects(self._lattice)
        for key, value in objects.iteritems():
            item = self._create_object_tree_item(key, value)
            self._objects_tree.addTopLevelItem(item)
            
        self._remove_object_button.setEnabled(False)

    def _refresh_influence_tree(self):
        self.clear_influence_tree()
        
        influencers = _get_all_influencers(self._lattice)
        for i in influencers:
            item = self._create_influencer_tree_item(i)
            self._influences_tree.addTopLevelItem(item)
            
        self._remove_influencer_button.setEnabled(False)
        
    def _interpolation_changed_from_maya(self):
        if not self._interpolation_changed_from_GUI:
            interpolation = cmds.getAttr(self._lattice + '.' + INTERPOLATION_ATTR)
            self._interpolation.setCurrentIndex(interpolation)
            self._max_bezier_recursion_lined_widget.setVisible(interpolation == 1)
        self._interpolation_changed_from_GUI = False
        
    def _max_bezier_recursion_changed_from_maya(self):
        if not self._max_bezier_recursion_changed_from_GUI:
            max_bezier_recursion = cmds.getAttr(self._lattice + '.' + MAX_BEZIER_RECURSION_ATTR)
            self._max_bezier_recursion.setValue(max_bezier_recursion)
        self._max_bezier_recursion_changed_from_GUI = False
        
    def _build_point_string(self, s, t, sD):
        return self._lattice + '.vtx[%d]' % (s + t * sD)
        
    def _start_script_jobs(self):
        id = cmds.scriptJob(attributeChange=[self._lattice + '.' + INTERPOLATION_ATTR, self._interpolation_changed_from_maya])
        self._script_jobs.append(id)
        id = cmds.scriptJob(attributeChange=[self._lattice + '.' + MAX_BEZIER_RECURSION_ATTR, self._max_bezier_recursion_changed_from_maya])
        self._script_jobs.append(id)
        
    def undo_triggered(self):
        if not self._lattice:
            return
        name = cmds.undoInfo(q=True, redoName=True)
        if str(name) in ['tcDeleteCameraLattice', 'tcAddObjectToCameraLattice', 'tcRemoveObjectFromCameraLattice']:
            self._refresh_object_tree()
        if str(name) in ['tcDeleteCameraLattice', 'tcAddInfluenceAreaToCameraLattice', 'tcRemoveInfluenceAreaFromCameraLattice',
                         'tcCreateInfluenceAreaToCameraLattice']:
            self._refresh_influence_tree()
        
    def redo_triggered(self):
        if not self._lattice:
            return
        name = cmds.undoInfo(q=True, undoName=True)
        if str(name) in ['tcDeleteCameraLattice', 'tcAddObjectToCameraLattice', 'tcRemoveObjectFromCameraLattice']:
            self._refresh_object_tree()
        if str(name) in ['tcDeleteCameraLattice', 'tcAddInfluenceAreaToCameraLattice', 'tcRemoveInfluenceAreaFromCameraLattice',
                         'tcCreateInfluenceAreaToCameraLattice']:
            self._refresh_influence_tree()
        
    def kill_script_jobs(self):
        for id in self._script_jobs:
            if cmds.scriptJob(exists=id):
                cmds.scriptJob(kill=id)
        self._script_jobs = []
        
        
class CameraLatticeWidget(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(CameraLatticeWidget, self).__init__(parent)
        self.setWindowTitle('Camera Lattice')
        self.setObjectName('Camera Lattice')
        
        self._main_layout = _build_layout(False)
        self.setLayout(self._main_layout)
        
        self._lattices = []
        
        self._script_jobs = []
        self._selected_camera = None
        
        self._combo_refreshing = False
        
        self._create_widgets()
        self._connect_signals()
        
    def _create_widgets(self):
        about = QtWidgets.QLabel()
        about.setPixmap(QtGui.QPixmap(_get_icons_path() + 'abouts.png'))
        self._main_layout.addWidget(about)
        
        self._main_layout.addWidget(_create_separator(False))
        
        h_layout = _build_layout(True)
        self._main_layout.addLayout(h_layout)
        
        v_layout = _build_layout(False)
        h_layout.addLayout(v_layout)
        
        self._camera_name = QtWidgets.QLabel()
        self._camera_name.setTextFormat(QtCore.Qt.RichText)
        v_layout.addWidget(LineWidget("Lattice Camera:", self._camera_name))
        
        h_layout2 = _build_layout(True)
        
        self._lattices_combo = QtWidgets.QComboBox()
        h_layout2.addWidget(LineWidget("Current Lattice:", self._lattices_combo))
        self._lattices_combo.setEnabled(False)
        self._refresh_button = QtWidgets.QPushButton()
        self._refresh_button.setIcon(QtGui.QIcon(_get_icons_path() + 'refreshIcon.png'))
        self._refresh_button.setIconSize(QtCore.QSize(18, 18))
        self._refresh_button.setFixedSize(20, 20)
        h_layout2.addWidget(self._refresh_button)
        self._refresh_button.setEnabled(False)
        
        v_layout.addLayout(h_layout2)
        self._set_camera_name('None')
        
        h_layout.addWidget(_create_separator(True))
        
        v_layout = _build_layout(False)
        h_layout.addLayout(v_layout)
        
        self._create_lattice_button = QtWidgets.QPushButton()
        self._create_lattice_button.setFixedSize(40, 40)
        self._create_lattice_button.setIcon(QtGui.QIcon(_get_icons_path() + 'addLattice.png'))
        self._create_lattice_button.setIconSize(QtCore.QSize(38, 38))
        self._create_lattice_button.setEnabled(False)
        self._delete_lattice_button = QtWidgets.QPushButton()
        self._delete_lattice_button.setIcon(QtGui.QIcon(_get_icons_path() + 'deleteLattice.png'))
        self._delete_lattice_button.setIconSize(QtCore.QSize(38, 38))
        self._delete_lattice_button.setFixedSize(40, 40)
        self._delete_lattice_button.setEnabled(False)
        
        v_layout.addWidget(self._create_lattice_button)
        v_layout.addWidget(self._delete_lattice_button)
        
        self._main_layout.addWidget(_create_separator())
        
        self._controls = CameraLatticeControlsWidget()
        self._controls.setEnabled(False)
        self._main_layout.addWidget(self._controls)
        
        self._main_layout.addWidget(QtWidgets.QWidget(), stretch=1)
    
    def _connect_signals(self):
        self._create_lattice_button.clicked.connect(self._create_lattice_button_clicked)
        self._delete_lattice_button.clicked.connect(self._delete_lattice_button_clicked)

        self._refresh_button.clicked.connect(self._refresh_widgets)
        
        self._lattices_combo.currentIndexChanged.connect(self._lattice_combo_changed)
    
    def _lattice_combo_changed(self, index):
        if not self._combo_refreshing and index != -1:
            cmds.undoInfo(openChunk=True, chunkName='tcCameraLatticeSelection')
            try:
                self._hide_all_lattices()
                cmds.setAttr(self._lattices[index]+".visibility", True)
                cmds.select(self._lattices[index], r=True)
            except:
                traceback.print_exc(file=sys.stdout)
            cmds.undoInfo(closeChunk=True)
            self._refresh_widgets(self._lattices[index])
            
    def _set_camera_name(self, name):
        self._camera_name.setText("<P><b><i><FONT COLOR='#000000' FONT SIZE = 4>" + name + "</i></b></P></br>")
        self._camera_name.setToolTip(name)
    
    def _create_lattice_button_clicked(self):
        x_div, y_div, ok = CameraLatticeCreateDialog.get_result()
        if ok:
            lattice = None
            cmds.undoInfo(openChunk=True, chunkName='tcCreateCameraLattice')
            try:
                lattice = _create_camera_lattice(self._selected_camera, x_div, y_div)
                self._hide_all_lattices()
            except:
                traceback.print_exc(file=sys.stdout)
            cmds.undoInfo(closeChunk=True)
            self._refresh_widgets(selected_lattice = lattice)
    
    def _delete_lattice_button_clicked(self):
        if self._lattices:
            cmds.undoInfo(openChunk=True, chunkName='tcDeleteCameraLattice')
            try:
                index = self._lattices_combo.currentIndex()
                _delete_lattice_deformers(self._lattices[index])
                cmds.delete(self._lattices[index])
                
                if len(self._lattices) > 1:
                    cmds.setAttr(self._lattices[1 if index == 0 else 0]+".visibility", True)
            except:
                traceback.print_exc(file=sys.stdout)
            cmds.undoInfo(closeChunk=True)
        self._refresh_widgets()
    
    def _refresh_lattices_combo(self, lattices):
        self._lattices = lattices

        self._lattices_combo.clear()
        
        self._lattices.sort()
        for l in self._lattices:
            self._lattices_combo.addItem(l.split("|")[-1])
            
    def _get_lattice_index(self, lattice):
        for i in range(len(self._lattices)):
            if lattice == self._lattices[i]:
                return i
        return -1

    def _hide_all_lattices(self):
        for l in self._lattices:
            cmds.setAttr(l+".visibility", False)
        
    def _get_selected_lattice(self):
        for l in self._lattices:
            if cmds.getAttr(l+".visibility"):
                return l

    def _refresh_widgets(self, selected_lattice = None):
        lattices = _get_lattices_from_camera(self._selected_camera)
        has_lattices = bool(lattices)
        
        self._controls.clear_object_tree()
        self._controls.clear_influence_tree()
        self._controls.setEnabled(has_lattices)
        
        self._delete_lattice_button.setEnabled(has_lattices)
        
        self._combo_refreshing = True
        
        self._lattices_combo.setEnabled(has_lattices)
        self._refresh_button.setEnabled(has_lattices)
        if has_lattices:
            self._refresh_lattices_combo(lattices)
            if not selected_lattice:
                selected_lattice = self._get_selected_lattice()
            
            self._lattices_combo.setCurrentIndex(self._get_lattice_index(selected_lattice))
            self._controls.set_lattice(selected_lattice)
        else:
            self._lattices = []
            self._lattices_combo.clear()

            self._controls.kill_script_jobs()
            self._controls._lattice = None
        
        self._combo_refreshing = False
        
    def _selection_changed(self):
        selection = cmds.ls(sl=True, l=True)
        camera = _get_camera(selection)
        
        if not camera or camera == self._selected_camera:
            return
        
        self._create_lattice_button.setEnabled(True)
        
        self._selected_camera = camera
        self._set_camera_name(self._selected_camera.split('|')[-1])
        self._refresh_widgets()
        
    def _start_script_jobs(self):
        self._script_jobs = []
        id = cmds.scriptJob(event=["SelectionChanged", self._selection_changed])
        self._script_jobs.append(id)
        id = cmds.scriptJob(event=["deleteAll", self._delete_all_triggered])
        self._script_jobs.append(id)
        id = cmds.scriptJob(event=["NameChanged", self._name_changed_triggered])
        self._script_jobs.append(id)
        id = cmds.scriptJob(event=["Undo", self._undo_triggered])
        self._script_jobs.append(id)
        id = cmds.scriptJob(event=["Redo", self._redo_triggered])
        self._script_jobs.append(id)
    
    def _undo_triggered(self):
        self._controls.undo_triggered()
        
        if self._selected_camera:
            name = cmds.undoInfo(q=True, redoName=True)
            if str(name) in ['tcCreateCameraLattice', 'tcDeleteCameraLattice', 'tcCameraLatticeSelection']:
                self._refresh_widgets()
                
    def _delete_all_triggered(self):
        self._selected_camera = None
        self._set_camera_name('None')
        
        self._controls.kill_script_jobs()
        self._controls._lattice = None
        self._controls.clear_object_tree()
        self._controls.clear_influence_tree()
        self._controls.setEnabled(False)
        
        self._create_lattice_button.setEnabled(False)
        self._delete_lattice_button.setEnabled(False)

        self._combo_refreshing = True
        self._lattices_combo.clear()
        self._lattices_combo.setEnabled(False)
        self._refresh_button.setEnabled(False)
        self._combo_refreshing = False
    
    def _redo_triggered(self):
        self._controls.redo_triggered()
        
        if self._selected_camera:
            name = cmds.undoInfo(q=True, undoName=True)
            if str(name) in ['tcCreateCameraLattice', 'tcDeleteCameraLattice', 'tcCameraLatticeSelection']:
                self._refresh_widgets()
                
    def _name_changed_triggered(self):
        if not self._selected_camera:
            return
        
        lattices = _get_lattices_from_camera(self._selected_camera)
        if not lattices:
            return 
        
        if self._was_lattice_renamed():
            self._combo_refreshing = True
            self._refresh_lattices_combo(lattices)
            selected_lattice = self._get_selected_lattice()
            self._lattices_combo.setCurrentIndex(self._get_lattice_index(selected_lattice))
            self._controls.set_lattice(selected_lattice)
            self._combo_refreshing = False
        else:
            self._controls._refresh_object_tree()
            self._controls._refresh_influence_tree()
    
    def _was_lattice_renamed(self):
        for l in self._lattices:
            if not cmds.objExists(l):
                return True
        return False
    
    def show(self):
        if self._selected_camera:
            self._refresh_widgets()
        super(CameraLatticeWidget, self).show()
    
    def closeEvent(self, event):
        for id in self._script_jobs:
            if cmds.scriptJob(exists=id):
                cmds.scriptJob(kill=id)
        self._script_jobs = []
        
        self._controls.kill_script_jobs()
        
        super(CameraLatticeWidget, self).closeEvent(event)
    
        
camera_lattice_widget = None
def get_camera_lattice_widget():
    global camera_lattice_widget
    if camera_lattice_widget is None:
        camera_lattice_widget = CameraLatticeWidget()
    return camera_lattice_widget

def run():
    if not cmds.pluginInfo('tcCameraLattice', q=1, l=1):
        cmds.loadPlugin('tcCameraLattice', quiet=True)
    
    w = get_camera_lattice_widget()
    w._start_script_jobs()
    w._selection_changed()
    w.show()
    w.raise_()

