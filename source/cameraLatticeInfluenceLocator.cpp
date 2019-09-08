//
//  cameraLatticeInfluenceLocator.cpp
//  cameraLattice
//
//  Created by Daniele Federico on 02/03/15.
//
//

#define PI 3.14159265358979323846
#define DEG2RAD(DEG) ((DEG)*((PI)/(180.0)))

#include <maya/MFnNumericAttribute.h>
#include <maya/MFnMessageAttribute.h>
#include <maya/MGlobal.h>
#include "cameraLatticeInfluenceLocator.h"

MObject CameraLatticeInfluenceLocator::falloff;
MObject CameraLatticeInfluenceLocator::message;
MTypeId CameraLatticeInfluenceLocator::id( 0x00122C04 );
MString	CameraLatticeInfluenceLocator::drawDbClassification("drawdb/geometry/cameraLatticeInfluenceArea");
MString	CameraLatticeInfluenceLocator::drawRegistrantId("tcCameraLatticeInfluenceNodePlugin");

CameraLatticeInfluenceLocator::CameraLatticeInfluenceLocator() {}
CameraLatticeInfluenceLocator::~CameraLatticeInfluenceLocator() {}

MStatus CameraLatticeInfluenceLocator::compute( const MPlug& /*plug*/, MDataBlock& /*data*/ )
{
	return MS::kUnknownParameter;
}

void CameraLatticeInfluenceLocator::drawCircle(const int axis, const double radius)
{
    glBegin(GL_LINE_LOOP);
    
    for (int i=0; i < 360; i+=4)
    {
        float degInRad = DEG2RAD(i);
        if (axis == 0)
            glVertex3f(cos(degInRad)*radius, sin(degInRad)*radius, 0);
        else if (axis == 1)
            glVertex3f(cos(degInRad)*radius, 0, sin(degInRad)*radius);
        else
            glVertex3f(0, cos(degInRad)*radius, sin(degInRad)*radius);
    }
    
    glEnd();
}

// called by legacy default viewport
void CameraLatticeInfluenceLocator::draw( M3dView & view, const MDagPath &path,
                     M3dView::DisplayStyle style,
                     M3dView::DisplayStatus status )
{
    if (status == M3dView::kInvisible)
        return;
    
	MPlug plug( thisMObject(), falloff );
	double falloffVal;
	plug.getValue( falloffVal );
    
	view.beginGL();
    
    view.setDrawColor(MHWRender::MGeometryUtilities::wireframeColor(path));
    
    /*
    if (status == M3dView::kActive || status == M3dView::kLead)
        view.setDrawColor( MColor( 0.8f, 1.0f, 0.8f, 1.0f )  );
    else
        view.setDrawColor( MColor( 0.0f, 0.0f, 0.3f, 1.0f ) );
    */

    drawCircle(0, 1);
	drawCircle(1, 1);
    drawCircle(2, 1);
    
    if (falloffVal < 0.02)
        falloffVal = 0.02;
    else if (falloffVal > 0.98)
        falloffVal = 0.98;
    falloffVal = 1 - falloffVal;
    
    view.setDrawColor( MColor( 1.0f, 0.0f, 0.0f, 0.5f ) );
    drawCircle(0, falloffVal);
    drawCircle(1, falloffVal);
    drawCircle(2, falloffVal);
    
    
	view.endGL();
}

bool CameraLatticeInfluenceLocator::isBounded() const
{
	return true;
}

MBoundingBox CameraLatticeInfluenceLocator::boundingBox() const
{
	// Get the size
	//
    
	MPoint corner1( -1, -1, -1 );
	MPoint corner2( 1, 1, 1 );
    
	return MBoundingBox( corner1, corner2 );
}

void* CameraLatticeInfluenceLocator::creator()
{
	return new CameraLatticeInfluenceLocator();
}

MStatus CameraLatticeInfluenceLocator::initialize()
{
	MFnUnitAttribute unitFn;
	MStatus			 stat;
    
    MFnNumericAttribute nAttr;
    
	falloff = nAttr.create( "falloff", "fa", MFnNumericData::kDouble);
    nAttr.setWritable(true);
	nAttr.setDefault(0.5);
    nAttr.setMin(0);
    nAttr.setMax(1);
    nAttr.setKeyable(true);
    nAttr.setConnectable(true);
    
    stat = addAttribute(falloff);
    if (!stat)
    {
		stat.perror("Failed while adding falloff attribute.");
		return stat;
	}
    
    MFnMessageAttribute msgAttr;
    message = msgAttr.create("locatorMessage", "lm");
    msgAttr.setArray(true);
    stat = addAttribute(message);
    if (!stat)
    {
		stat.perror("Failed while adding locatorMessage attribute.");
		return stat;
	}
    
	return MS::kSuccess;
}

//---------------------------------------------------------------------------
//---------------------------------------------------------------------------
// Viewport 2.0 override implementation
//---------------------------------------------------------------------------
//---------------------------------------------------------------------------


CameraLatticeInfluenceDrawOverride::CameraLatticeInfluenceDrawOverride(const MObject& obj)
: MHWRender::MPxDrawOverride(obj, NULL, false),
cameraLatticeInfluenceLocator(obj)
{
	fModelEditorChangedCbId = MEventMessage::addEventCallback(
		"modelEditorChanged", OnModelEditorChanged, this);
}

CameraLatticeInfluenceDrawOverride::~CameraLatticeInfluenceDrawOverride()
{
	if (fModelEditorChangedCbId != 0)
	{
		MMessage::removeCallback(fModelEditorChangedCbId);
		fModelEditorChangedCbId = 0;
	}
}

void CameraLatticeInfluenceDrawOverride::OnModelEditorChanged(void *clientData)
{
	// Mark the node as being dirty so that it can update on display mode switch,
	// e.g. between wireframe and shaded.
	CameraLatticeInfluenceDrawOverride *ovr = static_cast<CameraLatticeInfluenceDrawOverride*>(clientData);
	if (ovr) MHWRender::MRenderer::setGeometryDrawDirty(ovr->cameraLatticeInfluenceLocator);
}

MHWRender::DrawAPI CameraLatticeInfluenceDrawOverride::supportedDrawAPIs() const
{
	return MHWRender::kAllDevices;
}


bool CameraLatticeInfluenceDrawOverride::isBounded(const MDagPath& /*objPath*/,
                                      const MDagPath& /*cameraPath*/) const
{
	return true;
}

MBoundingBox CameraLatticeInfluenceDrawOverride::boundingBox(
                                                const MDagPath& objPath,
                                                const MDagPath& cameraPath) const
{
	MPoint corner1( -1, -1, -1 );
	MPoint corner2( 1, 1, 1 );
    
	CameraLatticeInfluenceDrawOverride *nonConstThis = (CameraLatticeInfluenceDrawOverride *)this;
	nonConstThis->mCurrentBoundingBox.clear();
	nonConstThis->mCurrentBoundingBox.expand( corner1 );
	nonConstThis->mCurrentBoundingBox.expand( corner2 );
    
	return mCurrentBoundingBox;
}

bool CameraLatticeInfluenceDrawOverride::disableInternalBoundingBoxDraw() const
{
	return false;
}

// Called by Maya each time the object needs to be drawn.
MUserData* CameraLatticeInfluenceDrawOverride::prepareForDraw(
                                                 const MDagPath& objPath,
                                                 const MDagPath& cameraPath,
                                                 const MHWRender::MFrameContext& frameContext,
                                                 MUserData* oldData)
{
	// Any data needed from the Maya dependency graph must be retrieved and cached in this stage.
	// There is one cache data for each drawable instance, if it is not desirable to allow Maya to handle data
	// caching, simply return null in this method and ignore user data parameter in draw callback method.
	// e.g. in this sample, we compute and cache the data for usage later when we create the
	// MUIDrawManager to draw CameraLatticeInfluence in method addUIDrawables().
	CameraLatticeInfluenceData* data = dynamic_cast<CameraLatticeInfluenceData*>(oldData);
	if (!data)
	{
		data = new CameraLatticeInfluenceData();
        data->center = MPoint(0,0,0);
        data->X = MVector(1,0,0);
        data->Y = MVector(0,1,0);
        data->Z = MVector(0,0,1);
	}
    

    MPlug plug( objPath.node(), CameraLatticeInfluenceLocator::falloff );
	plug.getValue(data->falloffVal);
    if (data->falloffVal < 0.02)
        data->falloffVal = 0.02;
    else if (data->falloffVal > 0.98)
        data->falloffVal = 0.98;
    data->falloffVal = 1 - data->falloffVal;
    
    // get correct color based on the state of object, e.g. active or dormant
	data->color = MHWRender::MGeometryUtilities::wireframeColor(objPath);
    
	return data;
}

// addUIDrawables() provides access to the MUIDrawManager, which can be used
// to queue up operations for drawing simple UI elements such as lines, circles and
// text. To enable addUIDrawables(), override hasUIDrawables() and make it return true.
void CameraLatticeInfluenceDrawOverride::addUIDrawables(
                                           const MDagPath& objPath,
                                           MHWRender::MUIDrawManager& drawManager,
                                           const MHWRender::MFrameContext& frameContext,
                                           const MUserData* data)
{
	// Get data cached by prepareForDraw() for each drawable instance, then MUIDrawManager
	// can draw simple UI by these data.
    
	CameraLatticeInfluenceData* pLocatorData = (CameraLatticeInfluenceData*)data;
	if (!pLocatorData)
	{
		return;
	}
    
	// Insert your custom drawing part here
	drawManager.beginDrawable();
    
	drawManager.setColor( pLocatorData->color );
#ifndef MAYA2014
	drawManager.setDepthPriority(5);
#endif    
    drawManager.circle(	pLocatorData->center, pLocatorData->X, 1, false);
    drawManager.circle(	pLocatorData->center, pLocatorData->Y, 1, false);
    drawManager.circle(	pLocatorData->center, pLocatorData->Z, 1, false);
    
    
    if (pLocatorData->falloffVal > 0)
    {
        drawManager.setColor( MColor(1.0f, 0.0f, 0.0f, 1.0f));
        drawManager.circle(	pLocatorData->center, pLocatorData->X, pLocatorData->falloffVal, false);
        drawManager.circle(	pLocatorData->center, pLocatorData->Y, pLocatorData->falloffVal, false);
        drawManager.circle(	pLocatorData->center, pLocatorData->Z, pLocatorData->falloffVal, false);
    }
    
	drawManager.endDrawable();
}
