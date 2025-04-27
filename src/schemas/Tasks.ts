import { Surreal } from "surrealdb";
// import { Task } from '@/types/Task';

export async function defineTasksSchema(db: Surreal) {
  try {
    await db.query(`
      DEFINE TABLE tasks SCHEMAFULL
        PERMISSIONS
          FOR select, create, update, delete FULL;

      DEFINE FIELD type ON tasks TYPE string;
      DEFINE FIELD identifier ON tasks TYPE string;
      DEFINE FIELD status ON tasks TYPE string;
      DEFINE FIELD result ON tasks TYPE string;
      DEFINE FIELD error ON tasks TYPE string;
    `);
    console.log("Defined tasks table schema from Tasks.ts.");
  } catch (err) {
    console.error("Error defining tasks table schema:", err);
  }
}
