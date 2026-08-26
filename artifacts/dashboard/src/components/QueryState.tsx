import { AlertCircle } from "lucide-react";

export function QueryError({ message = "Unable to load bot data. Check that the API server and Freqtrade are running." }: { message?: string }) {
  return (
    <div className="flex items-start gap-2 rounded-md border border-destructive/20 bg-destructive/10 p-3 text-destructive">
      <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
      <p className="text-xs">{message}</p>
    </div>
  );
}

export function QueryEmpty({ message }: { message: string }) {
  return <div className="py-10 text-center text-sm text-muted-foreground">{message}</div>;
}
