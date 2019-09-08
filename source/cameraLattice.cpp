
#include <string.h>
#include <maya/MIOStream.h>
#include <math.h>


#include <maya/MItMeshVertex.h>

#include <maya/MFnNumericAttribute.h> 
#include <maya/MFnMessageAttribute.h>
#include <maya/MFnMatrixAttribute.h>
#include <maya/MFnTypedAttribute.h>
#include <maya/MFnEnumAttribute.h>
#include <maya/MFnMeshData.h>
#include <maya/MFnData.h>
#include <maya/MFnMatrixData.h>
#include <maya/MPlugArray.h>
#include <maya/MFloatMatrix.h>

#include <maya/MFnCamera.h>
#include <maya/MFnMesh.h>
#include <maya/MFnDependencyNode.h>
#include <maya/MFnLatticeData.h>
#include <maya/MFnLattice.h>

#include <maya/MPlug.h>

#include <maya/MDataHandle.h>
#include <maya/MArrayDataHandle.h>

#include <maya/MPoint.h>
#include <maya/MVector.h>
#include <maya/MString.h>

#include <maya/MGlobal.h>

#include <maya/MDagModifier.h>

#include "cameraLattice.h"


double fac(int n)
{
	if (n == 0 || n == 1)
		return 1;
	else
		return n * fac(n-1) ;
}

double C(int i, int l)
{
	return fac(l) / (fac(i) * fac(l - i));
}

double B(int i, int l, double s)
{
	return C(i, l) * pow(s,i) * pow(1-s,l-i);
}

void findBoundaryCells(const double w, const int D, int &min, int &max)
{
	double step = 1.0/(D - 1);
	
	for (int i = 0; i < D - 1; i++)
	{
		double thisStep = step * i;
		if ((w < thisStep + step) && (w >= thisStep))
		{
			min = i;
			max = i+1;
			return;
		}
	}
    
    //in case we are outside the case (LEFT)
    if (w < 0)
    {
        min = 0;
        max = 1;
        return;
    }
    
    //in case we are outside the case (RIGHT)
	if (D > 2)
		min = D - 2;
	else
		min = D - 1;
	
	max = D - 1;
}

void findLinearDeformedPoint(MPoint &tempPoint, const MPointArray *planePoints, const float u, const float v, const int sD, const int tD)
{
    int minX, maxX, minY, maxY;
	findBoundaryCells(u, sD, minX, maxX);
	findBoundaryCells(v, tD, minY, maxY);
    
    //Finding projection factor on delimiting edges
	int factorX = sD - 1;
	int factorY = tD - 1;
	float uLocal = (u - float(minX) / factorX) / (float(maxX) / factorX - float(minX) / factorX);
	float vLocal = (v - float(minY) / factorY) / (float(maxY) / factorY - float(minY) / factorY);
	
	//find the edges --- aligned on the Y
	MPoint p1 = (*planePoints)[minX + minY * sD];
	MPoint p2 = (*planePoints)[minX + maxY * sD];
	MPoint p3 = (*planePoints)[maxX + minY * sD];
	MPoint p4 = (*planePoints)[maxX + maxY * sD];
	
	MPoint p21 = (p2 - p1) * vLocal + p1;
	MPoint p43 = (p4 - p3) * vLocal + p3;
	
	//finding the point between the edges -- this is on the X
	tempPoint = (p43 - p21) * uLocal + p21;
}

void findBezierDeformedPoint(MPoint &tempPoint, const MPointArray *planePoints, const float u, const float v, const int offsetS, const int offsetT, const int finalS, const int finalT, const int sD)
{
	MVector result, temp;
    
	for ( unsigned s = 0; s < finalS; s++)
		for ( unsigned t = 0; t < finalT; t++)
		{
            int index = offsetS + s + (offsetT + t) * sD;
			result += (*planePoints)[index] * B(s, finalS - 1, u) * B(t, finalT - 1, v);
		}
	tempPoint = result;
}

double get_influencers_weight(const MPoint &pt, const std::vector<Influencer> *influencers)
{
    MVector vec;
    
    double totalWeight = 0.0;
    for (unsigned int i = 0; i < influencers->size(); ++i)
    {
        const Influencer &influencer = (*influencers)[i];
        vec = pt - influencer.pos;
        if (vec.length() > influencer.maxAxisLength)
            continue;
        
        vec = pt * (*influencers)[i].invMat;

        double length = vec.length();
        //the radius of the locator in local space is 1
        if (length < 1)
        {
            if (length <= 0.0001 || influencer.falloff < 0.0001 || length < 1 - influencer.falloff)
                totalWeight = 1;
            else
                totalWeight += 1 - (length - (1 - influencer.falloff)) / influencer.falloff;
        }
        
        if (totalWeight >= 0.9999)
            return 1.0;
    }
    
    return totalWeight;
}

/**********************************************************
 CAMERA LATTICE DATA CLASS FOR TBB
 **********************************************************/

void CameraLatticeData::operator()( const tbb::blocked_range<size_t>& r ) const
{
    for( size_t i=r.begin(); i!=r.end(); ++i )
    {
        MPoint intialPosition = (*m_data.points)[i];
        
        double weight = m_data.envelopeValue;
        if ((*m_data.influencers).size() != 0)
            weight = m_data.envelopeValue * get_influencers_weight(intialPosition * (*m_data.toWorldMatrix), m_data.influencers);
        
        if (weight < 0.00001)
            continue;
        
        MPoint pt = intialPosition * *m_data.projectionMatrix;
        
        double zDepth = -pt[2];
        
        if (!m_data.isOrtho)
            pt = pt / zDepth;
        
        double u = pt.x / m_data.filmHAperture + 0.5;
        double v = pt.y / m_data.filmVAperture + 0.5;

        double gov = m_data.gateOffsetValue;
        if (u > 1.0 + gov || v > 1.0 + gov || u < 0.0 - gov || v < 0.0 - gov)
            continue;
        
        MPoint finalPoint;
        if (m_data.behaviour == 1)
        {
            // remapping the u and v
            int minX, maxX, minY, maxY;
            findBoundaryCells(u, m_data.sD, minX, maxX);
            findBoundaryCells(v, m_data.tD, minY, maxY);
            
            minX = minX - m_data.maxRecursion < 0 ? 0 : minX - m_data.maxRecursion;
            maxX = maxX + m_data.maxRecursion > m_data.sD ? m_data.sD: maxX + m_data.maxRecursion;
            minY = minY - m_data.maxRecursion < 0 ? 0 : minY - m_data.maxRecursion;
            maxY = maxY + m_data.maxRecursion > m_data.tD ? m_data.tD: maxY + m_data.maxRecursion;
            
            float minSU = float(minX) / (m_data.sD - 1); float maxSU = float(maxX - 1) / (m_data.sD - 1);
            u = (u - minSU) / (maxSU - minSU);
            
            double minTU = double(minY) / (m_data.tD - 1); double maxTU = double(maxY - 1) / (m_data.tD - 1);
            v = (v - minTU) / (maxTU - minTU);
            
            findBezierDeformedPoint(finalPoint, m_data.planePoints, u, v, minX, minY, maxX - minX, maxY - minY, m_data.sD);
        }
        else
            findLinearDeformedPoint(finalPoint, m_data.planePoints, u, v, m_data.sD, m_data.tD);
        
        //we map it back to the (-1,1) range
        finalPoint.x *= m_data.filmHAperture;
        finalPoint.y *= m_data.filmVAperture;
        finalPoint.z = pt.z;
        
        if (!m_data.isOrtho)
            finalPoint = finalPoint * zDepth;
        
        finalPoint *= *m_data.invProjectionMatrix;
        if (weight > 0.9999)
            (*m_data.deformedPoints)[i] = finalPoint;
        else
            (*m_data.deformedPoints)[i] = intialPosition + (finalPoint - intialPosition) * weight;

    }
};


/**********************************************************
 CAMERA LATTICE DEFORMER
 **********************************************************/

MTypeId     CameraLattice::id( 0x00122C01 );

// local attributes
//
MObject 	CameraLattice::inputLattice;
MObject		CameraLattice::interpolation;
MObject     CameraLattice::objectMatrix;
MObject     CameraLattice::deformerMessage;
MObject     CameraLattice::latticeToDeformerMessage;
MObject     CameraLattice::sSubidivision;
MObject     CameraLattice::tSubidivision;
MObject     CameraLattice::cameraMatrix;
MObject     CameraLattice::inOrtho;
MObject     CameraLattice::inOrthographicWidth;
MObject     CameraLattice::inVerticalFilmAperture;
MObject     CameraLattice::inHorizontalFilmAperture;
MObject     CameraLattice::inFocalLength;
MObject     CameraLattice::maxBezierRecursion;
MObject     CameraLattice::influenceFalloff;
MObject     CameraLattice::influenceMatrix;
MObject     CameraLattice::gateOffset;


CameraLattice::CameraLattice()
{
    refreshLogicalIndex = true;
    cachedLogicalIndex.clear();
}

CameraLattice::~CameraLattice() {}

void* CameraLattice::creator()
{
	return new CameraLattice();
}

MStatus CameraLattice::initialize()
{
    MFnMessageAttribute msgAttr;
    deformerMessage = msgAttr.create("deformerMessage", "dm");
    latticeToDeformerMessage = msgAttr.create("ldMessage", "ldm");
    
	MFnTypedAttribute tAttr;
	inputLattice = tAttr.create( "inputLattice", "il", MFnMeshData::kMesh );
	tAttr.setStorable( false );
	tAttr.setHidden( true );

    MFnMatrixAttribute  mAttr;
	objectMatrix = mAttr.create( "objectMatrix", "om");
	mAttr.setHidden( true );
    
	cameraMatrix = mAttr.create( "cameraMatrix", "cm");
	mAttr.setHidden( true );
    
    influenceMatrix = mAttr.create("influenceMatrix", "im");
    mAttr.setHidden( true );
    mAttr.setArray(true);
    
    MFnNumericAttribute nAttr;
	sSubidivision = nAttr.create( "sSubdivision", "ss", MFnNumericData::kLong);
    nAttr.setWritable(true);
	nAttr.setDefault(0);
    
	tSubidivision = nAttr.create( "tSubdivision", "ts", MFnNumericData::kLong);
    nAttr.setWritable(true);
	nAttr.setDefault(0);
    
    maxBezierRecursion = nAttr.create( "maxBezierRecursion", "mbr", MFnNumericData::kLong);
    nAttr.setWritable(true);
	nAttr.setDefault(10);
	
	MFnEnumAttribute enumAttr;
	interpolation = enumAttr.create("interpolation", "i", 0);
	enumAttr.addField("Linear", 0);
	enumAttr.addField("Bezier", 1);
    
    gateOffset = nAttr.create( "gateOffset", "go", MFnNumericData::kDouble);
  	nAttr.setDefault(0.05);
    nAttr.setChannelBox(true);
    nAttr.setMin(0);
    nAttr.setMax(1);
    
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
    
    influenceFalloff = nAttr.create("influenceFalloff", "iF", MFnNumericData::kDouble);
	nAttr.setDefault(0);
    nAttr.setArray(true);

	//  deformation attributes
    addAttribute(deformerMessage);
    addAttribute(latticeToDeformerMessage);
	addAttribute(inputLattice);
	addAttribute(objectMatrix);
    addAttribute(cameraMatrix);
    addAttribute(sSubidivision);
    addAttribute(tSubidivision);
	addAttribute(interpolation);
    addAttribute(inOrtho);
    addAttribute(inOrthographicWidth);
    addAttribute(inVerticalFilmAperture);
    addAttribute(inHorizontalFilmAperture);
    addAttribute(inFocalLength);
    addAttribute(maxBezierRecursion);
    addAttribute(influenceMatrix);
    addAttribute(influenceFalloff);
    addAttribute(gateOffset);
	
	attributeAffects(inputLattice, CameraLattice::outputGeom);
    attributeAffects(objectMatrix, CameraLattice::outputGeom);
    attributeAffects(cameraMatrix, CameraLattice::outputGeom);
	attributeAffects(interpolation, CameraLattice::outputGeom);
    attributeAffects(inOrtho, CameraLattice::outputGeom);
    attributeAffects(inOrthographicWidth, CameraLattice::outputGeom);
    attributeAffects(inVerticalFilmAperture, CameraLattice::outputGeom);
    attributeAffects(inHorizontalFilmAperture, CameraLattice::outputGeom);
    attributeAffects(inFocalLength, CameraLattice::outputGeom);
    attributeAffects(CameraLattice::maxBezierRecursion, CameraLattice::outputGeom);
    attributeAffects(CameraLattice::influenceMatrix, CameraLattice::outputGeom);
    attributeAffects(CameraLattice::influenceFalloff, CameraLattice::outputGeom);
    attributeAffects(CameraLattice::gateOffset, CameraLattice::outputGeom);

	return MStatus::kSuccess;
}

MStatus
CameraLattice::deform( MDataBlock& block,
				MItGeometry& iter,
				const MMatrix& m,
				unsigned int multiIndex)
//
// Method: deform
//
// Description:   Deform the point with a squash algorithm
//
// Arguments:
//   block		: the datablock of the node
//	 iter		: an iterator for the geometry to be deformed
//   m    		: matrix to transform the point into world space
//	 multiIndex : the index of the geometry that we are deforming
//
//
{
	MStatus returnStatus;
	
	// Envelope data from the base class.
	// The envelope is simply a scale factor.
	//
	MDataHandle envData = block.inputValue(envelope, &returnStatus);
	if (MS::kSuccess != returnStatus) return returnStatus;
	float envelopeValue = envData.asFloat();
	if (envelopeValue < 0.01)	 return returnStatus;
    
    bool isOrtho = block.inputValue(inOrtho).asBool();
    double ortographicWidth = block.inputValue(inOrthographicWidth).asDouble();
    
    double horizontalAperture = block.inputValue(inHorizontalFilmAperture).asDouble();
    double verticalAperture = block.inputValue(inVerticalFilmAperture).asDouble();
    double focalLength = block.inputValue(inFocalLength).asDouble();
    double gateOffsetValue =block.inputValue(gateOffset).asDouble();
    
    double filmHAperture, filmVAperture;
    if (isOrtho)
    {
        filmHAperture = ortographicWidth;
        filmVAperture = ortographicWidth;
    }
    else
    {
        // 0.03937 is the factor mm to inches
        // 57.29578 is the maya conversion factor
        double hFov = 57.29578 * 2.0 * atan((0.5 * horizontalAperture) / (focalLength * 0.03937));
        double vFov = 57.29578 * 2.0 * atan((0.5 * verticalAperture) / (focalLength * 0.03937));

        //PLEASE NOTE: while the projected points which needs to be deformed are in a range (-1, 1),
        //              but we want it to go between 0 and 1 to find the final deformation, that's the multiplication by 2
        
        // 3.14159265/180.f is the conversion to radians
        filmHAperture = tan((hFov*0.5) * 3.14159265 / 180.f) * 2;
        filmVAperture = tan((vFov*0.5) * 3.14159265 / 180.f) * 2;
    }
    
    std::vector<Influencer> influencers;
    MArrayDataHandle iFalloffArrayHandle = block.inputArrayValue(influenceFalloff);
    MArrayDataHandle iMatrixArrayHandle = block.inputArrayValue(influenceMatrix);
    int count = iFalloffArrayHandle.elementCount();
    if (count != iMatrixArrayHandle.elementCount())
    {
        MGlobal::displayWarning("tcCameraLatticeDeformer: something is wrong with your influence area connection. Ignoring influence areas.");
    }
    else
    {

        if (refreshLogicalIndex)
        {
            //we need to do this here as connectionMade and connectionBroken are called before the connections are made
            MPlug falloffPlug(thisMObject(), influenceFalloff);
            unsigned int numConnectedElements = falloffPlug.numConnectedElements();
            cachedLogicalIndex.clear();
            for (unsigned int i = 0; i < numConnectedElements; i++)
            {
                MPlug tempPlug = falloffPlug.connectionByPhysicalIndex(i);
                if (tempPlug.isSource()) continue;
                cachedLogicalIndex.append(tempPlug.logicalIndex());
            }
            
            refreshLogicalIndex = false;
        }

        if (cachedLogicalIndex.length() > 0)
        {
            influencers.reserve(cachedLogicalIndex.length());
            MVector vec;
            for (unsigned int i = 0; i < cachedLogicalIndex.length(); i++)
            {
                iFalloffArrayHandle.jumpToArrayElement(cachedLogicalIndex[i]);
                iMatrixArrayHandle.jumpToArrayElement(cachedLogicalIndex[i]);
                
                Influencer influencer;
                influencer.falloff = iFalloffArrayHandle.inputValue().asDouble();
                MMatrix mat = iMatrixArrayHandle.inputValue().asMatrix();
                influencer.invMat = mat.inverse();
                
                influencer.pos.x = mat[3][0];
                influencer.pos.y = mat[3][1];
                influencer.pos.z = mat[3][2];
                
                vec.x = mat[0][0];
                vec.y = mat[0][1];
                vec.z = mat[0][2];
                influencer.maxAxisLength = vec.length();
                
                vec.x = mat[1][0];
                vec.y = mat[1][1];
                vec.z = mat[1][2];
                double thisLength = vec.length();
                if (thisLength > influencer.maxAxisLength)
                    influencer.maxAxisLength = thisLength;
                
                vec.x = mat[2][0];
                vec.y = mat[2][1];
                vec.z = mat[2][2];
                thisLength = vec.length();
                if (thisLength > influencer.maxAxisLength)
                    influencer.maxAxisLength = thisLength;
                    
                influencers.push_back(influencer);
            }
        }
    }
    
    
	int sD = block.inputValue(sSubidivision).asInt();
    int tD = block.inputValue(tSubidivision).asInt();
    
    int maxRecursion = block.inputValue(maxBezierRecursion).asInt();
    
    MDataHandle inputLatticeHnd = block.inputValue(inputLattice);
    MFnMesh planeMesh(inputLatticeHnd.asMesh());
    MPointArray planePoints;
    planeMesh.getPoints(planePoints);
    
    if (planePoints.length() == 0 || planePoints.length() != sD * tD)
        return MStatus::kFailure;
    
	int behaviour = block.inputValue(interpolation).asShort();
    
    MDataHandle matData = block.inputValue(objectMatrix);
	MMatrix objMat = matData.asMatrix();
    
    matData = block.inputValue(cameraMatrix);
	MMatrix camMat = matData.asMatrix();
    
    MMatrix projectionMatrix = objMat * camMat.inverse();
    MMatrix invProjectionMatrix = camMat * objMat.inverse();

    MPointArray points, deformedPoints;
    iter.allPositions(points);
    
    deformedPoints.copy(points);
    
    CameraLatticeData dataObj(&projectionMatrix, &invProjectionMatrix, &objMat, &points, &deformedPoints, &planePoints, filmHAperture, filmVAperture, sD, tD, isOrtho, maxRecursion, behaviour, &influencers, gateOffsetValue, envelopeValue);
    tbb::parallel_for(tbb::blocked_range<size_t>(0, points.length()), dataObj);

    iter.setAllPositions(deformedPoints);
    
	return MS::kSuccess;
}

MStatus CameraLattice::connectionMade (const MPlug &plug, const MPlug &otherPlug, bool asSrc)
{
    if (plug == influenceFalloff || plug == influenceMatrix)
    {
        refreshLogicalIndex = true;
    }
    
    return MPxDeformerNode::connectionMade(plug, otherPlug, asSrc);
}

MStatus CameraLattice::connectionBroken (const MPlug &plug, const MPlug &otherPlug, bool asSrc)
{
    if (plug == influenceFalloff || plug == influenceMatrix)
    {
        refreshLogicalIndex = true;
    }
    
    return MPxDeformerNode::connectionBroken(plug, otherPlug, asSrc);
}




