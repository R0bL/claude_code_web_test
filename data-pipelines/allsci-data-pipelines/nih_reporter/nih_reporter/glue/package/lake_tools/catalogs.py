from .transformations import *


class Catalog:
    def __init__(self, params=None):
        self.catalog = {}
        self.params = params or {}

    def __getitem__(self, catalog_item):
        if catalog_item not in self.catalog:
            raise ValueError(f"Catalog item {catalog_item} not found")

        return self.catalog[catalog_item](**self.params)

    
class TransformationCatalog(Catalog):
    def __init__(self):
        super().__init__()
        self.catalog = {    
            "nih_reporter_projects": NihReporterProjects,
            "nih_reporter_organizations": NihReporterOrganizations,
            "nih_reporter_principal_investigators": NihReporterPrincipalInvestigators,
            "nih_reporter_program_officers": NihReporterProgramOfficers,
            "nih_reporter_publications": NihReporterPublications,
            "nih_reporter_clinical_trials": NihReporterClinicalTrials,
            "nih_reporter_agencies_admin": NihReporterAgenciesAdmin,
            "nih_reporter_agencies_funding": NihReporterAgenciesFunding,
            "nih_reporter_spending_categories": NihReporterSpendingCategories,
            "nih_reporter_terms": NihReporterTerms,
            "nih_reporter_study_sections": NihReporterStudySections,
        }
