# start_dask_async.py
import asyncio
from distributed import Scheduler, Worker, Client

async def main():
    # scheduler with dashboard
    async with Scheduler(dashboard_address=":8787", port=8786) as s:
        # one CPU-tagged worker, single thread
        async with Worker(
            s.address,
            nthreads=1,
            resources={"cpu": 1},
        ) as cpu_w, \
        Worker(
            s.address,
            nthreads=1,
            resources={"gpu": 1},
        ) as gpu_w:
            # connect client in async mode
            client = await Client(s.address, asynchronous=True)
            print("Scheduler:", s.address)
            print("Dashboard:", client.dashboard_link)

            # keep alive until interrupted
            try:
                await asyncio.Event().wait()
            except (KeyboardInterrupt, SystemExit):
                pass
            finally:
                await client.close()  # valid/awaitable in async mode

if __name__ == "__main__":
    asyncio.run(main())
