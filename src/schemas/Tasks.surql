DEFINE TABLE tasks
    PERMISSIONS
        FOR select, create, update, delete FULL;

DEFINE FIELD type ON tasks TYPE string;
DEFINE FIELD identifier ON tasks TYPE string;
DEFINE FIELD status ON tasks TYPE string;
DEFINE FIELD result ON tasks TYPE string;
DEFINE FIELD error ON tasks TYPE string;
