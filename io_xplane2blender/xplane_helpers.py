# File: xplane_helpers.py
# Defines Helpers

from typing import Any, Callable, Dict, List, Optional, Union, TextIO
import bpy
import mathutils

import datetime
from datetime import timezone
import os
import re

import io_xplane2blender
from io_xplane2blender import xplane_config
from io_xplane2blender import xplane_constants

FLOAT_PRECISION = 8

def floatToStr(n):
    s = '0'
    n = round(n, FLOAT_PRECISION)
    n_int = int(n)

    if n_int == n:
        s = '%d' % n_int
    else:
        s = (('%.' + str(FLOAT_PRECISION) + 'f') % n).rstrip('0')

    return s

def getColorAndLitTextureSlots(mat):
    texture = None
    textureLit = None

    for slot in mat.texture_slots:
        if slot and slot.use and slot.texture and slot.texture.type == 'IMAGE':
            if slot.use_map_color_diffuse:
                texture = slot
            elif slot.use_map_emit:
                textureLit = slot

    return texture, textureLit

def resolveBlenderPath(path:str)->str:
    blenddir = os.path.dirname(bpy.context.blend_data.filepath)

    if path[0:2] == '//':
        return os.path.join(blenddir, path[2:])
    else:
        return path


def get_addon_resources_dir()->str:
    return os.path.join(os.path.dirname(__file__),"resources")


def get_potential_objects_in_layer(layer_idx: int, scene: bpy.types.Scene)->List[bpy.types.Object]:
    '''
    Returns roughly what xplane_file will collect in a Layer Mode
    export, taking into account only object type and layer, not its visibilty
    '''
    assert layer_idx in range(0,20), "Layer must be between 0 and 19"

    return list(
            filter(
                lambda obj: obj.layers[layer_idx] and obj.type in {"MESH", "LAMP", "ARMATURE", "EMPTY"},
                scene.objects))


def get_potential_objects_in_root_object(root_object: bpy.types.Object)->List[bpy.types.Object]:
    assert root_object.xplane.isExportableRoot, "Must be Root Object"
    def collect_children(obj: bpy.types.Object)->List[bpy.types.Object]:
        objects = [] # type: List[bpy.types.Object]
        for child in obj.children:
            if child.type in {"MESH", "LAMP", "ARMATURE", "EMPTY"}:
                objects.append(child)
            objects.extend(collect_children(child))
        return objects
    return collect_children(root_object)


def get_root_objects_in_scene(scene: bpy.types.Scene)->List[bpy.types.Object]:
    return [obj for obj in scene.objects if obj.xplane.isExportableRoot]


def vec_b_to_x(v):
    return mathutils.Vector((v.x, v.z, -v.y))


def vec_x_to_b(v):
    return mathutils.Vector((v.x, -v.z, v.y))


# This is a convience struct to help prevent people from having to repeat copy and paste
# a tuple of all the members of XPlane2BlenderVersion. It is only a data transport struct!
class VerStruct():
    def __init__(self,addon_version=None,build_type=None,build_type_version=None,data_model_version=None,build_number=None):
        self.addon_version      = tuple(addon_version) if addon_version      is not None else (0,0,0)
        self.build_type         = build_type           if build_type         is not None else xplane_constants.BUILD_TYPE_DEV
        self.build_type_version = build_type_version   if build_type_version is not None else 0
        self.data_model_version = data_model_version   if data_model_version is not None else 0
        self.build_number       = build_number         if build_number       is not None else xplane_constants.BUILD_NUMBER_NONE

    def __eq__(self,other):
        if tuple(self.addon_version) == tuple(other.addon_version):
            if self.build_type == other.build_type:
                if self.build_type_version == other.build_type_version:
                    if self.data_model_version == other.data_model_version:
                        return True
        return False

    def __ne__(self,other):
        return not self == other

    def __lt__(self,other):
        return (self.addon_version,xplane_constants.BUILD_TYPES.index(self.build_type),self.build_type_version,self.data_model_version) <\
               (other.addon_version,xplane_constants.BUILD_TYPES.index(other.build_type),other.build_type_version,other.data_model_version)

    def __gt__(self,other):
        return (self.addon_version,xplane_constants.BUILD_TYPES.index(self.build_type),self.build_type_version,self.data_model_version) >\
               (other.addon_version,xplane_constants.BUILD_TYPES.index(other.build_type),other.build_type_version,other.data_model_version)

    def __ge__(self, other):
        return (self > other) or (self == other)

    def __le__(self, other):
        return (self < other) or (self == other)

    #Works for XPlane2BlenderVersion or VerStruct
    def __repr__(self):
        #WARNING! Make sure this is the same as XPlane2BlenderVersion's!!!
        return "(%s, %s, %s, %s, %s)" % ('(' + ','.join(map(str,self.addon_version)) + ')',
                                         "'" + str(self.build_type) + "'",
                                               str(self.build_type_version),
                                               str(self.data_model_version),
                                         "'" + str(self.build_number) + "'")

    def __str__(self):
        #WARNING! Make sure this is the same as XPlane2BlenderVersion's!!!
        return "%s-%s.%s+%s.%s" % ('.'.join(map(str,self.addon_version)),
                                   self.build_type,
                                   self.build_type_version,
                                   self.data_model_version,
                                   self.build_number)

    # Method: is_valid
    #
    # Tests if all members of VerStruct are the right type and semantically valid
    # according to our spec
    #
    # Returns True or False
    def is_valid(self):
        types_correct = isinstance(self.addon_version,tuple) and len(self.addon_version) == 3 and\
                        isinstance(self.build_type,str)         and \
                        isinstance(self.build_type_version,int) and \
                        isinstance(self.data_model_version,int) and \
                        isinstance(self.build_number,str)

        if not types_correct:
            raise TypeError("Incorrect types passed into VerStruct")

        if (self.addon_version[0]  >= 3
            and self.addon_version[1] >= 0
            and self.addon_version[2] >= 0
            or self.addon_version == (2, 49, 2)):
            if xplane_constants.BUILD_TYPES.index(self.build_type) != -1:
                if self.build_type == xplane_constants.BUILD_TYPE_DEV or \
                    self.build_type == xplane_constants.BUILD_TYPE_LEGACY:
                    if self.build_type_version > 0:
                        print("build_type_version must be 0 when build_type is %s" % self.build_type)
                        return False
                elif self.build_type_version <= 0:
                        print("build_type_version must be > 0 when build_type is %s" % self.build_type)
                        return False

                if self.build_type == xplane_constants.BUILD_TYPE_LEGACY and self.data_model_version != 0:
                    print("Invalid build_type,data_model_version combo: legacy and data_model_version is not 0")
                    return False
                elif self.build_type != xplane_constants.BUILD_TYPE_LEGACY and self.data_model_version <= 0:
                    print("Invalid build_type,data_model_version combo: non-legacy and data_model_version is > 0")
                    return False

                if self.build_number == xplane_constants.BUILD_NUMBER_NONE:
                    return True
                else:
                    datetime_matches = re.match(r"(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", self.build_number)
                    try:
                        # a timezone aware datetime object preforms the validations on construction.
                        dt = datetime.datetime(*[int(group) for group in datetime_matches.groups()],tzinfo=timezone.utc)
                    except Exception as e:
                        print('Exception %s occurred while trying to parse datetime' % e)
                        print('"%s" is an invalid build number' % (self.build_number))
                        return False
                    else:
                        return True
            else:
                print("build_type %s was not found in BUILD_TYPES" % self.build_type)
        else:
            print("addon_version %s is invalid" % str(self.addon_version))
            return False

    @staticmethod
    def add_to_version_history(version_to_add):
        history = bpy.context.scene.xplane.xplane2blender_ver_history

        if len(history) == 0 or history[-1].name != repr(version_to_add):
            new_hist_entry = history.add()
            new_hist_entry.name = repr(version_to_add)
            success = new_hist_entry.safe_set_version_data(version_to_add.addon_version,
                                                           version_to_add.build_type,
                                                           version_to_add.build_type_version,
                                                           version_to_add.data_model_version,
                                                           version_to_add.build_number)
            if not success:
                history.remove(len(history)-1)
                return None
            else:
                return new_hist_entry
        else:
            return False

    # Method: current
    #
    # Returns a VerStruct with all the current xplane_config information.
    # Note: This SHOULD be the same as scene.xplane.xplane2blender_ver, and it is better to use that version.
    # This is provided to reduce error-prone copy and pasting, as needed only!

    @staticmethod
    def current():
        return VerStruct(xplane_config.CURRENT_ADDON_VERSION,
                         xplane_config.CURRENT_BUILD_TYPE,
                         xplane_config.CURRENT_BUILD_TYPE_VERSION,
                         xplane_config.CURRENT_DATA_MODEL_VERSION,
                         xplane_config.CURRENT_BUILD_NUMBER)

    @staticmethod
    def make_new_build_number():
        #Use the UNIX Timestamp in UTC
        return datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%d%H%M%S")

    # Method: parse_version
    #
    # Parameters:
    #    version_string: The string to attempt to parse
    # Returns:
    # A valid XPlane2BlenderVersion.VerStruct or None if the parse was unsuccessful
    #
    # Parses a variety of strings and attempts to extract a valid version number and a build number
    # Formats
    # Old version numbers: '3.2.0', '3.2', or '3.3.13'
    # New, moder format: '3.4.0-beta.5+1.20170906154330'
    @staticmethod
    def parse_version(version_str:str)->Optional['VerStruct']:
        version_struct = VerStruct()
        #We're dealing with modern
        if version_str.find('-') != -1:
            ######################################
            # Regex matching and data extraction #
            ######################################
            format_str = r"(\d+\.\d+\.\d+)-(alpha|beta|dev|leg|rc)\.(\d+)"

            if '+' in version_str:
                format_str += r"\+(\d+)\.(\w{14})"

            version_matches = re.match(format_str,version_str)

            # Part 1: Major.Minor.revision (1)
            # Part 2: '-' and a build type (2), then a literal '.' and build type number (3)
            # (Optional) literal '+'
                # Part 3: 1 or more digits for data model number (4), a literal '.',
                # then a YYYYMMDDHHMMSS (5)
            if version_matches:
                version_struct.addon_version      = tuple([int(comp) for comp in version_matches.group(1).split('.')])
                version_struct.build_type         = version_matches.group(2)
                version_struct.build_type_version = int(version_matches.group(3))

                #If we have a build number, we can take this opportunity to validate it
                if '+' in version_str:
                    version_struct.data_model_version = int(version_matches.group(4))
                    #Regex groups for (hopefully matching) YYYYMMDDHHMMSS
                    version_struct.build_number = version_matches.group(5)
            else:
                return None
        else:
            if re.search("[^\d.]",version_str) is not None:
                return None
            else:
                version_struct.addon_version = tuple([int(v) for v in version_str.split('.')])
                version_struct.build_type = xplane_constants.BUILD_TYPE_LEGACY

        if version_struct.is_valid():
            return version_struct
        else:
            return None


class XPlaneLogger():
    """A logger somewhat similar (but not as robust) as Python's logger"""
    def __init__(self):
        self.transports = [] # type: Dict[str, Union[str, List[str]]]
        self.messages = [] # type: List[str]

    def addTransport(self, transport: Callable[[str, str, Any], None], messageTypes: Optional[List[str]]=None)->None:
        if messageTypes is None:
            messageTypes = ['error', 'warning', 'info', 'success']
        self.transports.append({
            'fn': transport,
            'types': messageTypes
        })

    def clear(self):
        self.clearTransports()
        self.clearMessages()

    def clearTransports(self):
        del self.transports[:]

    def clearMessages(self):
        del self.messages[:]

    def messagesToString(self, messages = None):
        if messages == None:
            messages = self.messages

        out = ''

        for message in messages:
            out += XPlaneLogger.messageToString(message['type'], message['message'], message['context']) + '\n'

        return out

    def log(self, messageType: str, message: str, context: Any = None):
        """
        Currently there is one known use of 'context', "raw" means supress the "INFO:" or other type
        portion of a message
        """
        self.messages.append({
            'type': messageType,
            'message': message,
            'context': context
        })

        for transport in self.transports:
            if messageType in transport['types']:
                transport['fn'](messageType, message, context)

    def error(self, message: str, context: Any = None):
        self.log('error', message, context)

    def warn(self, message: str, context: Any = None):
        self.log('warning', message, context)

    def info(self, message: str, context: Any = None):
        self.log('info', message, context)

    def success(self, message: str, context: Any = None):
        self.log('success', message, context)

    def findOfType(self, messageType: str)->bool:
        return list(filter(lambda message: message['type'] == messageType, self.messages))

    def hasOfType(self, messageType: str)->bool:
        return any(message['type'] == messageType for message in self.messages)

    def findErrors(self)->List[str]:
        return self.findOfType('error')

    def hasErrors(self)->bool:
        return self.hasOfType('error')

    def findWarnings(self)->List[str]:
        return self.findOfType('warning')

    def hasWarnings(self)->bool:
        return self.hasOfType('warning')

    def findInfos(self)->List[str]:
        return self.findOfType('info')

    def hasInfos(self)->bool:
        return self.hasOfType('info')

    @staticmethod
    def messageToString(messageType: str, message: str, context: Any=None):
        if context == 'raw':
            return '%s' % (message)
        else:
            return '%s: %s' % (messageType.upper(), message)

    @staticmethod
    def InternalTextTransport(name: Optional[str] = None):
        if name is None:
            name = 'XPlane2Blender.log'
        if bpy.data.texts.find(name) == -1:
            log = bpy.data.texts.new(name)
        else:
            log = bpy.data.texts[name]

        log.clear()

        def transport(messageType: str, message: str, context: Any = None):
            log.write(XPlaneLogger.messageToString(messageType, message, context) + '\n')

        return transport

    @staticmethod
    def ConsoleTransport():
        def transport(messageType: str, message: str, context: Any = None):
            print(XPlaneLogger.messageToString(messageType, message, context))

        return transport

    @staticmethod
    def FileTransport(filehandle: TextIO):
        def transport(messageType: str, message: str, context: Any = None):
            filehandle.write(XPlaneLogger.messageToString(messageType, message, context) + '\n')

        return transport


logger = XPlaneLogger()

