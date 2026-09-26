import { Button } from './Button';

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="p-4 flex flex-col items-start gap-2">
      <p className="text-band-critical-text text-[13px]">{message}</p>
      {onRetry !== undefined && (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
