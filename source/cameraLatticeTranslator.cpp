/*
 *  CameraLatticeTranslator.cpp
 *  CameraLatticeTranslator
 *
 *
 */

#include "cameraLatticeTranslator.h"

MTypeId CameraLatticeTranslator::id( 0x00122C02 );

MObject CameraLatticeTranslator::inNearClipPlane;
MObject CameraLatticeTranslator::inFocalLength;
MObject CameraLatticeTranslator::inHorizontalFilmAperture;
MObject CameraLatticeTranslator::inVerticalFilmAperture;
MObject CameraLatticeTranslator::outScaleX;
MObject CameraLatticeTranslator::outScaleY;
MObject CameraLatticeTranslator::outTranslateZ;
MObject CameraLatticeTranslator::inOrtho;
MObject CameraLatticeTranslator::inOrthographicWidth;

void *CameraLatticeTranslator::creator()
{
	return new CameraLatticeTranslator();
}

MStatus CameraLatticeTranslator::compute( const MPlug& plug, MDataBlock& data )
{
	MStatus stat;
	
	if (plug == outScaleX || plug == outScaleY)
	{
        
		double nearClipPlane = data.inputValue(inNearClipPlane).asDouble();
        double w = data.inputValue(inHorizontalFilmAperture).asDouble() * 25.4;  //25.4 is the inch to meter factor, the film aperture is store in inches
   		double h = data.inputValue(inVerticalFilmAperture).asDouble() * 25.4;
   		double focalLength = data.inputValue(inFocalLength).asDouble();
        
        bool isOrtho = data.inputValue(inOrtho).asBool();
        double ortographicWidth = data.inputValue(inOrthographicWidth).asDouble();
        
        double scaleX, scaleY;
        if (!isOrtho)
        {
            double wfov = 2.0 * atan(0.5 * w / focalLength );
            double hfov = 2.0 * atan(0.5 * h / focalLength );
        
            scaleX = 2.0 * tan( wfov / 2.0 ) * nearClipPlane;
            scaleY = 2.0 * tan( hfov / 2.0 ) * nearClipPlane;
        }
        else
        {
            scaleX = ortographicWidth;
            scaleY = ortographicWidth;
        }
        
        MDataHandle outScaleXHandle = data.outputValue(outScaleX);
        MDataHandle outScaleYHandle = data.outputValue(outScaleY);
        outScaleXHandle.setDouble(scaleX);
        outScaleYHandle.setDouble(scaleY);
        
        outScaleXHandle.setClean();
        outScaleYHandle.setClean();
		
		data.setClean( plug );
	}
    else if (plug == outTranslateZ)
    {
        double nearClipPlane = data.inputValue(inNearClipPlane).asDouble();
        MDataHandle outTranslateXHandle = data.outputValue(outTranslateZ);
        
        bool isOrtho = data.inputValue(inOrtho).asBool();
        double offset = isOrtho ? 0.04: 0.0001;
        
        // we add an extra tiny offset so the lattice is visible
        outTranslateXHandle.setDouble(nearClipPlane * -1 - offset);
        outTranslateXHandle.setClean();
        data.setClean(plug);
    }
	return stat;
}


MStatus CameraLatticeTranslator::initialize()
{
	MFnNumericAttribute nAttr;

	outScaleX = nAttr.create( "outScaleX", "oSX", MFnNumericData::kDouble);
    nAttr.setWritable(false);
	nAttr.setDefault(0);
	outScaleY = nAttr.create( "outScaleY", "oSY", MFnNumericData::kDouble);
    nAttr.setWritable(false);
	nAttr.setDefault(0);
    
    outTranslateZ = nAttr.create( "outTranslateZ", "oTZ", MFnNumericData::kDouble);
    nAttr.setWritable(false);
	nAttr.setDefault(0);
    
	inNearClipPlane = nAttr.create( "inNearClipPlane", "iNC", MFnNumericData::kDouble);
	nAttr.setDefault(0);
    
    inFocalLength = nAttr.create( "inFocalLength", "iFL", MFnNumericData::kDouble);
	nAttr.setDefault(0);
    
    inHorizontalFilmAperture = nAttr.create( "inHorizontalFilmAperture", "iHF", MFnNumericData::kDouble);
	nAttr.setDefault(0);
    
    inVerticalFilmAperture = nAttr.create( "inVerticalFilmAperture", "iVF", MFnNumericData::kDouble);
	nAttr.setDefault(0);
    
    inOrthographicWidth = nAttr.create( "inOrthographicWidth", "iOW", MFnNumericData::kDouble);
	nAttr.setDefault(0);
    
    inOrtho = nAttr.create("inOrtho", "iO", MFnNumericData::kBoolean);
    nAttr.setDefault(false);
    
	addAttribute(outScaleX );
	addAttribute(outScaleY );
	addAttribute(outTranslateZ );
	addAttribute(inNearClipPlane );
	addAttribute(inFocalLength );
	addAttribute(inHorizontalFilmAperture );
	addAttribute(inVerticalFilmAperture );
    addAttribute(inOrtho );
    addAttribute(inOrthographicWidth );

	attributeAffects(inNearClipPlane, outScaleX );
	attributeAffects(inFocalLength, outScaleX );
	attributeAffects(inHorizontalFilmAperture, outScaleX );
	attributeAffects(inVerticalFilmAperture, outScaleX );
    attributeAffects(inNearClipPlane, outScaleY );
	attributeAffects(inFocalLength, outScaleY );
	attributeAffects(inHorizontalFilmAperture, outScaleY );
	attributeAffects(inVerticalFilmAperture, outScaleY );
    
    attributeAffects(inOrtho, outScaleX );
    attributeAffects(inOrtho, outScaleY );

    attributeAffects(inOrthographicWidth, outScaleX );
    attributeAffects(inOrthographicWidth, outScaleY );
    
    attributeAffects(inOrtho, outTranslateZ);
    attributeAffects(inNearClipPlane, outTranslateZ );
	
	return MS::kSuccess;
}
