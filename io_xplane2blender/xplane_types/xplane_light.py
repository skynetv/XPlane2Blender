from .xplane_object import XPlaneObject
from ..xplane_helpers import floatToStr

# Class: XPlaneLight
# A Light
#
# Extends:
#   <XPlaneObject>
class XPlaneLight(XPlaneObject):
    # Property: indices
    # list - [start,end] Starting end ending indices for this light.

    # Property: color
    # list - [r,g,b] Color taken from the original Blender light. Can change depending on <lightType>.

    # Property: energy
    # float - Energy taken from Blender light.

    # Property: lightType
    # string - Type of the light taken from <XPlaneLampSettings>.

    # Property: size
    # float - Size of the light taken from <XPlaneLampSettings>.

    # Property: lightName
    # string - Name of the light taken from <XPlaneLampSettings>.

    # Property: params
    # string - Parameters taken from <XPlaneLampSettings>.

    # Property: dataref
    # string - Dataref path taken from <XPlaneLampSettings>.

    # Constructor: __init__
    #
    # Parameters:
    #   object - A Blender object
    def __init__(self, blenderObject):
        super(XPlaneLight, self).__init__(blenderObject)
        self.indices = [0,0]
        self.color = [blenderObject.data.color[0], blenderObject.data.color[1], blenderObject.data.color[2]]
        self.energy = blenderObject.data.energy
        self.type = 'LIGHT'
        self.lightType = blenderObject.data.xplane.type
        self.size = blenderObject.data.xplane.size
        self.lightName = blenderObject.data.xplane.name
        self.params = blenderObject.data.xplane.params
        self.uv = blenderObject.data.xplane.uv
        self.dataref = blenderObject.data.xplane.dataref

        # change color according to type
        if self.lightType == 'flashing':
            self.color[0] = -self.color[0]
        elif self.lightType == 'pulsing':
            self.color[0] = 9.9
            self.color[1] = 9.9
            self.color[2] = 9.9
        elif self.lightType == 'strobe':
            self.color[0] = 9.8
            self.color[1] = 9.8
            self.color[2] = 9.8
        elif self.lightType == 'traffic':
            self.color[0] = 9.7
            self.color[1] = 9.7
            self.color[2] = 9.7

        self.getWeight(10000)

    def write(self):
        indent = self.xplaneBone.getIndent()
        o = super(XPlaneLight, self).write()

        # rendering (do not render lights with no indices)
        if self.indices[1] > self.indices[0]:
            bakeMatrix = self.xplaneBone.getBakeMatrix()

            translation = bakeMatrix.to_translation()

            if self.lightType == "named":
                o += "%sLIGHT_NAMED\t%s\t%s\t%s\t%s\n" % (
                    indent, self.lightName,
                    floatToStr(translation[0]),
                    floatToStr(translation[2]),
                    floatToStr(-translation[1])
                )
            elif self.lightType == "param":
                o += "%sLIGHT_PARAM\t%s\t%6.8f\t%6.8f\t%6.8f\t%s\n" % (
                    indent, self.lightName,
                    floatToStr(translation[0]),
                    floatToStr(translation[2]),
                    floatToStr(-translation[1]),
                    self.params
                )
            elif self.lightType == "custom":
                o += "%sLIGHT_CUSTOM\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" % (
                    indent,
                    floatToStr(translation[0]),
                    floatToStr(translation[2]),
                    floatToStr(-translation[1]),
                    floatToStr(self.color[0]),
                    floatToStr(self.color[1]),
                    floatToStr(self.color[2]),
                    floatToStr(self.energy),
                    floatToStr(self.size),
                    floatToStr(self.uv[0]),
                    floatToStr(self.uv[1]),
                    floatToStr(self.uv[2]),
                    floatToStr(self.uv[3]),
                    self.dataref
                )
            else:
                offset = self.indices[0]
                count = self.indices[1] - self.indices[0]
                o += "%sLIGHTS\t%d %d\n" % (indent, offset, count)

        return o
