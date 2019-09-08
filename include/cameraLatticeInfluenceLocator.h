

#ifndef CAMERA_LATTICE_INFLUENCE_LOCATOR_H
#define CAMERA_LATTICE_INFLUENCE_LOCATOR_H

#include <maya/MPxLocatorNode.h>
#include <maya/MString.h>
#include <maya/MTypeId.h>
#include <maya/MPlug.h>
#include <maya/MVector.h>
#include <maya/MDataBlock.h>
#include <maya/MDataHandle.h>
#include <maya/MColor.h>
#include <maya/M3dView.h>
#include <maya/MDistance.h>
#include <maya/MFnUnitAttribute.h>
#include <maya/MEventMessage.h>

// Viewport 2.0 includes
#include <maya/MDrawRegistry.h>
#include <maya/MPxDrawOverride.h>
#include <maya/MUserData.h>
#include <maya/MDrawContext.h>
#include <maya/MHWGeometryUtilities.h>
#include <maya/MPointArray.h>

class CameraLatticeInfluenceLocator : public MPxLocatorNode
{
public:
	CameraLatticeInfluenceLocator();
	virtual ~CameraLatticeInfluenceLocator();
    
    virtual MStatus   		compute( const MPlug& plug, MDataBlock& data );
    
	virtual void            draw( M3dView & view, const MDagPath & path,
                                 M3dView::DisplayStyle style,
                                 M3dView::DisplayStatus status );
    
	virtual bool            isBounded() const;
	virtual MBoundingBox    boundingBox() const;
    
	static  void *          creator();
	static  MStatus         initialize();
    
    void    drawCircle(const int axis, const double radius);
    
    // the falloff of the influencer
	static  MObject         falloff;
    static  MObject         message;
    
public:
	static	MTypeId		id;
	static	MString		drawDbClassification;
	static	MString		drawRegistrantId;
};

class CameraLatticeInfluenceData : public MUserData
{
public:
	CameraLatticeInfluenceData() : MUserData(false) {} // don't delete after draw
	virtual ~CameraLatticeInfluenceData() {}
    
	MColor color;
    MPoint center;
    MVector X, Y, Z;
	double falloffVal;
};

class CameraLatticeInfluenceDrawOverride : public MHWRender::MPxDrawOverride
{
public:
	static MHWRender::MPxDrawOverride* Creator(const MObject& obj)
	{
		return new CameraLatticeInfluenceDrawOverride(obj);
	}
    
	virtual ~CameraLatticeInfluenceDrawOverride();
    
	virtual MHWRender::DrawAPI supportedDrawAPIs() const;
    
	virtual bool isBounded(
                           const MDagPath& objPath,
                           const MDagPath& cameraPath) const;

	virtual bool disableInternalBoundingBoxDraw() const;
    
	virtual MBoundingBox boundingBox(
                                     const MDagPath& objPath,
                                     const MDagPath& cameraPath) const;
    
	virtual MUserData* prepareForDraw(
                                      const MDagPath& objPath,
                                      const MDagPath& cameraPath,
                                      const MHWRender::MFrameContext& frameContext,
                                      MUserData* oldData);
    
	virtual bool hasUIDrawables() const { return true; }
    
	virtual void addUIDrawables(
                                const MDagPath& objPath,
                                MHWRender::MUIDrawManager& drawManager,
                                const MHWRender::MFrameContext& frameContext,
                                const MUserData* data);
    
	static void draw(const MHWRender::MDrawContext& context, const MUserData* data) {};
    
protected:
	MBoundingBox mCurrentBoundingBox;
	MCallbackId fModelEditorChangedCbId;
	MObject cameraLatticeInfluenceLocator;
private:
	CameraLatticeInfluenceDrawOverride(const MObject& obj);
	float getMultiplier(const MDagPath& objPath) const;

	static void OnModelEditorChanged(void *clientData);
};

#endif
