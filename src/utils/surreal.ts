import { Surreal } from 'surrealdb';
import { surrealdbWasmEngines } from '@surrealdb/wasm';

interface DbConfig {
  url: string;
  namespace: string;
  database: string;
  user?: string;
  pass?: string;
}

// Store the default credentials separately
const DEFAULT_USER = "root";
const DEFAULT_PASS = "root";

const DEFAULT_CONFIG: DbConfig = { // Move DEFAULT_CONFIG outside of the component
  url: import.meta.env.VITE_SURREAL_URL || "indxdb://demo", 
  namespace: import.meta.env.VITE_SURREAL_NAMESPACE || "test",
  database: import.meta.env.VITE_SURREAL_DATABASE || "test",
  user: import.meta.env.VITE_SURREAL_USER || DEFAULT_USER,
  pass: import.meta.env.VITE_SURREAL_PASS || DEFAULT_PASS,
};

export const getDb = async (config: Partial<DbConfig> = {}): Promise<Surreal> => {
  const db = new Surreal({
    engines: surrealdbWasmEngines(),
  });

  const finalConfig: DbConfig = {
    url: config.url ?? DEFAULT_CONFIG.url,
    namespace: config.namespace ?? DEFAULT_CONFIG.namespace,
    database: config.database ?? DEFAULT_CONFIG.database,
    user: config.user ?? DEFAULT_CONFIG.user,
    pass: config.pass ?? DEFAULT_CONFIG.pass,
  };

  try {
    console.log(`getDb: Connecting to ${finalConfig.url}...`);
    await db.connect(finalConfig.url);
    console.log(`getDb: Using namespace: ${finalConfig.namespace}, database: ${finalConfig.database}`);
    await db.use({ namespace: finalConfig.namespace, database: finalConfig.database });

    const userIsDefault = finalConfig.user === DEFAULT_USER;
    const passIsDefault = finalConfig.pass === DEFAULT_PASS;
    const userWasSetExplicitly = import.meta.env.VITE_SURREAL_USER !== undefined || config.user !== undefined;
    const passWasSetExplicitly = import.meta.env.VITE_SURREAL_PASS !== undefined || config.pass !== undefined;

    if (finalConfig.user && finalConfig.pass && (!userIsDefault || !passIsDefault || (userWasSetExplicitly && passWasSetExplicitly))) {
      console.log(`getDb: Attempting signin as user: ${finalConfig.user}`);
      try {
          await db.signin({
            username: finalConfig.user,
            password: finalConfig.pass,
          });
          console.log(`getDb: Signed in successfully as ${finalConfig.user}`);
      } catch (authError) {
          console.error(`getDb: Signin failed for user ${finalConfig.user}:`, authError instanceof Error ? authError.message : String(authError));
          throw authError;
      }

    } else {
        console.log("getDb: Skipping signin (using default credentials or none provided/needed).");
    }

    console.log("getDb: Connection ready.");
    return db;
  } catch (err) {
    console.error("getDb: Failed during connection or setup:", err instanceof Error ? err.message : String(err));
    await db.close();
    throw err;
  }
};
