//
//  PluginMain.cpp
//  cameraLattice
//
//  Created by Daniele Federico on 14/12/14.
//
//

#include <maya/MFnPlugin.h>
#include <maya/MGlobal.h>
#include "cameraLattice.h"
#include "cameraLatticeTranslator.h"
#include "cameraLatticeInfluenceLocator.h"

extern "C" { FILE __iob_func[3] = { *stdin,*stdout,*stderr }; }


MStatus initializePlugin( MObject obj )
{
	MStatus status = MStatus::kSuccess;
	MFnPlugin plugin( obj, "ToolChefs_CameraLattice", "1.1", "Any");
    MString errorString;

	std::string licenseName = "tcAnimationTools";
	std::string product = "tcCameraLattice";

	int count = 1;
	const char *ver = "1.0";  

	status = plugin.registerNode( "tcCameraLatticeDeformer", CameraLattice::id, CameraLattice::creator, CameraLattice::initialize, MPxNode::kDeformerNode );
    if(!status)
	{
		MGlobal::displayError("tcCameraLatticeDeformer failed registration");
		return status;
	}
    
    status = plugin.registerNode( "tcCameraLatticeTranslator", CameraLatticeTranslator::id, CameraLatticeTranslator::creator,
                                 CameraLatticeTranslator::initialize);
    if(!status)
	{
		MGlobal::displayError("tcCameraLatticeTranslator failed registration");
		return status;
	}
    
    status = plugin.registerNode("tcCameraLatticeInfluenceAreaLocator",
                                 CameraLatticeInfluenceLocator::id,
                                 &CameraLatticeInfluenceLocator::creator,
                                 &CameraLatticeInfluenceLocator::initialize,
                                 MPxNode::kLocatorNode,
                                 &CameraLatticeInfluenceLocator::drawDbClassification);
	if (!status) {
		status.perror("tcCameraLatticeInfluenceAreaLocator failed registration");
		return status;
	}
    
    status = MHWRender::MDrawRegistry::registerDrawOverrideCreator(
                                                                   CameraLatticeInfluenceLocator::drawDbClassification,
                                                                   CameraLatticeInfluenceLocator::drawRegistrantId,
                                                                   CameraLatticeInfluenceDrawOverride::Creator);
	if (!status) {
		status.perror("tcCameraLatticeInfluenceLocator failed registerDrawOverrideCreator");
		return status;
	}
    
	MString addMenu;
	addMenu +=
	"global proc loadTcCameraLattice()\
	{\
		python(\"from tcCameraLattice import tcCameraLattice\\ntcCameraLattice.run()\");\
	}\
	\
	global proc addTcCameraLatticeToShelf()\
	{\
		global string $gShelfTopLevel;\
		\
		string $shelves[] = `tabLayout - q - childArray $gShelfTopLevel`;\
		string $shelfName = \"\";\
		int $shelfFound = 0;\
		for ($shelfName in $shelves)\
		{\
			if ($shelfName == \"Toolchefs\")\
			{\
				$shelfFound = 1;\
			}\
		}\
		if ($shelfFound == 0)\
		{\
			addNewShelfTab \"Toolchefs\";\
		}\
		\
		string $buttons[] = `shelfLayout -q -childArray \"Toolchefs\"`;\
		int $buttonExists = 0;\
		for ($button in $buttons)\
		{\
			string $lab = `shelfButton - q - label $button`;\
			if ($lab == \"tcCameraLattice\")\
			{\
				$buttonExists = 1;\
				break;\
			}\
		}\
		\
		if ($buttonExists == 0)\
		{\
			string $myButton = `shelfButton\
			-parent Toolchefs\
			-enable 1\
			-width 34\
			-height 34\
			-manage 1\
			-visible 1\
			-annotation \"Load tcCameraLattice\"\
			-label \"tcCameraLattice\"\
			-image1 \"tcCameraLattice.png\"\
			-style \"iconOnly\"\
			-sourceType \"python\"\
			-command \"from tcCameraLattice import tcCameraLattice\\ntcCameraLattice.run()\" tcCameraLatticeShelfButton`;\
		}\
	}\
	global proc addTcCameraLatticeToMenu()\
	{\
		global string $gMainWindow;\
		global string $showToolochefsMenuCtrl;\
		if (!(`menu - exists $showToolochefsMenuCtrl`))\
		{\
			string $name = \"Toolchefs\";\
			$showToolochefsMenuCtrl = `menu -p $gMainWindow -to true -l $name`;\
			string $tcToolsMenu = `menuItem -subMenu true -label \"Tools\" -p $showToolochefsMenuCtrl \"tcToolsMenu\"`;\
			menuItem -label \"Load tcCameraLattice\" -p $tcToolsMenu -c \"loadTcCameraLattice\" \"tcActiveCameraLatticeItem\";\
		}\
		else\
		{\
			int $deformerMenuExist = false;\
			string $defMenu = \"\";\
			string $subitems[] = `menu -q -itemArray $showToolochefsMenuCtrl`;\
			for ($item in $subitems)\
			{\
				if ($item == \"tcToolsMenu\")\
				{\
					$deformerMenuExist = true;\
					$defMenu = $item;\
					break;\
				}\
			}\
			if (!($deformerMenuExist))\
			{\
				string $tcToolsMenu = `menuItem -subMenu true -label \"Tools\" -p $showToolochefsMenuCtrl \"tcToolsMenu\"`;\
				menuItem -label \"Load tcCameraLattice\" -p $tcToolsMenu -c \"loadTcCameraLattice\" \"tcActiveCameraLatticeItem\";\
			}\
			else\
			{\
				string $subitems2[] = `menu -q -itemArray \"tcToolsMenu\"`;\
				int $deformerExists = 0;\
				for ($item in $subitems2)\
				{\
					if ($item == \"tcActiveCameraLatticeItem\")\
					{\
						$deformerExists = true;\
						break;\
					}\
				}\
				if (!$deformerExists)\
				{\
					menuItem -label \"Load tcCameraLattice\" -p $defMenu -c \"loadTcCameraLattice\" \"tcActiveCameraLatticeItem\";\
				}\
			}\
		}\
	};addTcCameraLatticeToMenu();addTcCameraLatticeToShelf();";
	MGlobal::executeCommand(addMenu, false, false);

	return status;
}

MStatus uninitializePlugin( MObject obj)
{
	MStatus status = MStatus::kSuccess;
	MFnPlugin plugin( obj );
	status = plugin.deregisterNode( CameraLattice::id );
    if (!status)
	{
		MGlobal::displayError("Error deregistering node tcCameraLatticeDeformer");
		return status;
	}
    
    status = plugin.deregisterNode( CameraLatticeTranslator::id );
    if (!status)
	{
		MGlobal::displayError("Error deregistering node tcCameraLatticeTranslator");
		return status;
	}
    
    status = MHWRender::MDrawRegistry::deregisterDrawOverrideCreator(
                                                                     CameraLatticeInfluenceLocator::drawDbClassification,
                                                                     CameraLatticeInfluenceLocator::drawRegistrantId);
	if (!status) {
		status.perror("Error deregistering drawOverrideCreator for tcCameraLatticeInfluenceAreaLocator");
		return status;
	}
    
    status = plugin.deregisterNode( CameraLatticeInfluenceLocator::id );
	if (!status) {
		status.perror("Error deregistering node tcCameraLatticeInfluenceAreaLocator");
		return status;
	}
    
    
	return status;
}
